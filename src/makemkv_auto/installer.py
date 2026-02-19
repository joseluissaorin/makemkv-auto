"""MakeMKV installation management."""

import re
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Optional

import requests
from rich.console import Console

from makemkv_auto.constants import MAKEMKV_DOWNLOAD_URL
from makemkv_auto.logger import get_logger

logger = get_logger(__name__)
console = Console()


class MakeMKVInstaller:
    """Manages MakeMKV installation."""
    
    DEPENDENCIES = [
        "build-essential",
        "pkg-config",
        "libc6-dev",
        "libssl-dev",
        "libexpat1-dev",
        "libavcodec-dev",
        "libgl1-mesa-dev",
        "qtbase5-dev",
        "zlib1g-dev",
        "wget",
        "curl",
        "libfdk-aac-dev",
        "libssl3",
        "libqt5widgets5",
        "jq",
        "sed",
        "grep",
        "eject",
    ]
    
    def __init__(self, version: str, prefix: Path = Path("/usr/local")) -> None:
        self.version = version
        self.prefix = prefix
        self.temp_dir = Path("/tmp/makemkv-build")
        self.oss_dir: Optional[Path] = None
        self.bin_dir: Optional[Path] = None
    
    def is_installed(self) -> bool:
        """Check if MakeMKV is already installed."""
        return shutil.which("makemkvcon") is not None
    
    def install_dependencies(self) -> None:
        """Install build dependencies."""
        logger.info("Installing dependencies...")
        
        try:
            subprocess.run(
                ["apt-get", "update"],
                check=True,
                capture_output=True,
            )
            
            subprocess.run(
                ["apt-get", "install", "-y"] + self.DEPENDENCIES,
                check=True,
                capture_output=True,
            )
            
            logger.info("Dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install dependencies: {e}")
            raise
    
    def download(self) -> None:
        """Download MakeMKV source archives."""
        logger.info(f"Downloading MakeMKV {self.version}...")
        
        # Clean and create temp directory
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        self.temp_dir.mkdir(parents=True)
        
        # Download URLs
        oss_url = f"{MAKEMKV_DOWNLOAD_URL}/makemkv-oss-{self.version}.tar.gz"
        bin_url = f"{MAKEMKV_DOWNLOAD_URL}/makemkv-bin-{self.version}.tar.gz"
        
        # Download OSS
        oss_archive = self.temp_dir / "makemkv-oss.tar.gz"
        self._download_file(oss_url, oss_archive)
        
        # Download BIN
        bin_archive = self.temp_dir / "makemkv-bin.tar.gz"
        self._download_file(bin_url, bin_archive)
        
        # Extract
        with tarfile.open(oss_archive, "r:gz") as tar:
            tar.extractall(self.temp_dir)
        
        with tarfile.open(bin_archive, "r:gz") as tar:
            tar.extractall(self.temp_dir)
        
        # Find extracted directories
        for item in self.temp_dir.iterdir():
            if item.is_dir():
                if "oss" in item.name:
                    self.oss_dir = item
                elif "bin" in item.name:
                    self.bin_dir = item
        
        if not self.oss_dir or not self.bin_dir:
            raise RuntimeError("Failed to extract MakeMKV archives")
        
        logger.info("Download and extraction complete")
    
    def _download_file(self, url: str, destination: Path) -> None:
        """Download a file with progress."""
        response = requests.get(url, stream=True, timeout=120)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        with open(destination, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    logger.debug(f"Downloaded {percent:.1f}%")
    
    def build_oss(self) -> None:
        """Build MakeMKV OSS component."""
        if not self.oss_dir:
            raise RuntimeError("OSS directory not set. Run download() first.")
        
        logger.info("Building MakeMKV OSS...")
        
        try:
            # Configure
            configure_cmd = ["./configure"]
            
            # Check for FDK-AAC
            if shutil.which("pkg-config"):
                result = subprocess.run(
                    ["pkg-config", "--exists", "fdk-aac"],
                    capture_output=True,
                )
                if result.returncode == 0:
                    configure_cmd.append("--enable-fdk-aac")
            
            subprocess.run(
                configure_cmd,
                cwd=self.oss_dir,
                check=True,
            )
            
            # Build
            subprocess.run(
                ["make", f"-j{self._get_cpu_count()}"],
                cwd=self.oss_dir,
                check=True,
            )
            
            # Install
            subprocess.run(
                ["make", "install"],
                cwd=self.oss_dir,
                check=True,
            )
            
            logger.info("MakeMKV OSS built and installed")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to build OSS: {e}")
            raise
    
    def build_bin(self) -> None:
        """Build MakeMKV BIN component."""
        if not self.bin_dir:
            raise RuntimeError("BIN directory not set. Run download() first.")
        
        logger.info("Building MakeMKV BIN...")
        
        try:
            # Build with auto-accept license
            result = subprocess.run(
                ["make", "install"],
                cwd=self.bin_dir,
                input="yes\n",
                capture_output=True,
                text=True,
                check=True,
            )
            
            logger.info("MakeMKV BIN built and installed")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to build BIN: {e}")
            raise
    
    def _get_cpu_count(self) -> int:
        """Get number of CPU cores."""
        try:
            return int(subprocess.run(
                ["nproc"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip())
        except (subprocess.CalledProcessError, ValueError):
            return 1
    
    def cleanup(self) -> None:
        """Clean up temporary files."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            logger.info("Cleaned up temporary files")
