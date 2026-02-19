"""Disc ripping and analysis functionality."""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from makemkv_auto.config import Config
from makemkv_auto.exceptions import DiscError, NoDiscError, RipError
from makemkv_auto.logger import get_logger

logger = get_logger(__name__)


class ContentType(Enum):
    """Content type enumeration."""
    MOVIE = "movie"
    TV_SHOW = "tvshow"
    UNKNOWN = "unknown"


@dataclass
class TitleInfo:
    """Information about a single title."""
    index: int
    duration: int  # seconds
    size_bytes: int
    content_type: str


@dataclass
class DiscInfo:
    """Information about a disc."""
    name: str
    sanitized_name: str
    content_type: ContentType
    confidence: str
    titles: list[TitleInfo]


class DiscAnalyzer:
    """Analyzes disc content to determine type and metadata."""
    
    def __init__(self, config: Config) -> None:
        self.config = config
    
    def get_disc_info(self) -> DiscInfo:
        """Get information about the disc in the drive."""
        device = self.config.devices.primary
        
        # Check if disc is present
        if not self._is_disc_present(device):
            raise NoDiscError(f"No disc detected in {device}")
        
        # Get disc info from makemkvcon
        info_output = self._get_makemkv_info(device)
        
        # Parse disc info
        disc_name = self._extract_disc_name(info_output)
        titles = self._extract_titles(info_output)
        
        # Determine content type
        content_type, confidence = self._detect_content_type(titles, disc_name)
        
        return DiscInfo(
            name=disc_name,
            sanitized_name=self._sanitize_name(disc_name),
            content_type=content_type,
            confidence=confidence,
            titles=titles,
        )
    
    def _is_disc_present(self, device: str) -> bool:
        """Check if a disc is present in the drive."""
        try:
            result = subprocess.run(
                ["makemkvcon", "-r", "--cache=1", "info", f"dev:{device}"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            # Check for DRV lines with actual disc data (non-empty name field)
            # DRV:0,2,999,1,"drive_name","disc_name","/dev/sr0"
            for line in result.stdout.split('\n'):
                if line.startswith('DRV:'):
                    parts = line.split('","')
                    if len(parts) >= 3:
                        # Check if disc name is present (not empty)
                        disc_name = parts[1].strip('"')
                        if disc_name:
                            return True
            return False
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            return False
        except FileNotFoundError:
            raise DiscError("makemkvcon not found. Is MakeMKV installed?")
    
    def _get_makemkv_info(self, device: str) -> str:
        """Get raw info output from makemkvcon."""
        try:
            result = subprocess.run(
                ["makemkvcon", "-r", "--cache=1", "info", f"dev:{device}"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout
        except subprocess.TimeoutExpired:
            raise DiscError("Timeout getting disc info")
        except subprocess.CalledProcessError as e:
            raise DiscError(f"Failed to get disc info: {e}")
    
    def _extract_disc_name(self, info_output: str) -> str:
        """Extract disc name from makemkvcon output."""
        # Try CINFO:2,0 first (disc name)
        match = re.search(r'^CINFO:2,0,"([^"]+)"', info_output, re.MULTILINE)
        if match:
            name = match.group(1).strip()
            if name:
                return name
        
        # Fallback to CINFO:0,1 (volume name)
        match = re.search(r'^CINFO:0,1,"([^"]+)"', info_output, re.MULTILINE)
        if match:
            return match.group(1).strip()
        
        return "Unknown_Disc"
    
    def _extract_titles(self, info_output: str) -> list[TitleInfo]:
        """Extract title information from makemkvcon output."""
        titles = []
        
        # Parse TINFO lines
        title_pattern = re.compile(r'^TINFO:(\d+),(\d+),\d+,"([^"]*)"', re.MULTILINE)
        
        titles_data: dict[int, dict] = {}
        
        for match in title_pattern.finditer(info_output):
            title_idx = int(match.group(1))
            info_type = int(match.group(2))
            value = match.group(3)
            
            if title_idx not in titles_data:
                titles_data[title_idx] = {}
            
            if info_type == 9:  # Duration
                # Parse HH:MM:SS format
                duration_match = re.match(r'(\d+):(\d+):(\d+)', value)
                if duration_match:
                    hours = int(duration_match.group(1))
                    minutes = int(duration_match.group(2))
                    seconds = int(duration_match.group(3))
                    titles_data[title_idx]['duration'] = hours * 3600 + minutes * 60 + seconds
            elif info_type == 10:  # Size
                try:
                    titles_data[title_idx]['size'] = int(value)
                except ValueError:
                    pass
        
        # Create TitleInfo objects
        for idx, data in sorted(titles_data.items()):
            duration = data.get('duration', 0)
            size = data.get('size', 0)
            
            # Determine content type based on duration
            duration_min = duration // 60
            if (self.config.detection.min_episode_duration <= duration_min <= 
                self.config.detection.max_episode_duration):
                content_type = "episode"
            elif duration_min >= self.config.detection.min_movie_duration:
                content_type = "movie"
            else:
                content_type = "extra"
            
            titles.append(TitleInfo(
                index=idx,
                duration=duration,
                size_bytes=size,
                content_type=content_type,
            ))
        
        return titles
    
    def _detect_content_type(self, titles: list[TitleInfo], disc_name: str) -> tuple[ContentType, str]:
        """Detect if disc contains movie or TV show content."""
        episodes = 0
        movies = 0
        
        for title in titles:
            if title.content_type == "episode":
                episodes += 1
            elif title.content_type == "movie":
                movies += 1
        
        # Check disc name for TV indicators
        name_lower = disc_name.lower()
        tv_indicators = ['season', 'series', 'episodes', 'temporada', 'episodios', 'disc']
        has_tv_indicator = any(indicator in name_lower for indicator in tv_indicators)
        
        # Determine type
        if episodes >= 2 and movies <= 1:
            return ContentType.TV_SHOW, "high"
        elif movies >= 1 and episodes <= 1:
            return ContentType.MOVIE, "high"
        elif has_tv_indicator:
            return ContentType.TV_SHOW, "high"
        elif movies >= 1:
            return ContentType.MOVIE, "medium"
        else:
            return ContentType.UNKNOWN, "low"
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize disc name for use as directory name."""
        # Replace invalid characters
        sanitized = re.sub(r'[\\/:*?"<>|]', '-', name)
        # Remove extra whitespace
        sanitized = ' '.join(sanitized.split())
        return sanitized.strip()


class Ripper:
    """Handles disc ripping operations."""
    
    def __init__(self, config: Config) -> None:
        self.config = config
    
    def rip_disc(self, disc_info: DiscInfo, output_path: Path, state_manager=None) -> None:
        """Rip disc to output directory with optional progress tracking."""
        device = self.config.devices.primary
        output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Ripping disc: {disc_info.name}")
        logger.info(f"Output: {output_path}")
        
        try:
            # Run makemkvcon with real-time output parsing
            process = subprocess.Popen(
                [
                    "makemkvcon",
                    "mkv",
                    f"dev:{device}",
                    "all",
                    str(output_path),
                    "--progress=-same",
                    f"--minlength={self.config.output.min_length}",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
            )
            
            stdout_lines = []
            stderr_lines = []
            current_title = 0
            total_titles = disc_info.titles if hasattr(disc_info, 'titles') else 0
            if total_titles:
                total_titles = len(total_titles)
            else:
                total_titles = 0
            
            # Parse output in real-time
            while True:
                stdout_line = process.stdout.readline() if process.stdout else ''
                stderr_line = process.stderr.readline() if process.stderr else ''
                
                if stdout_line:
                    stdout_lines.append(stdout_line)
                    # Parse progress from output
                    # Look for patterns like "Saving title X of Y" or progress indicators
                    title_match = re.search(r'Title #(\d+)', stdout_line)
                    if title_match:
                        current_title = int(title_match.group(1))
                    
                    # Update state if state_manager provided
                    if state_manager and total_titles > 0:
                        progress = (current_title / total_titles) * 100
                        state_manager.update_progress(
                            current_title=current_title,
                            progress_percent=progress
                        )
                
                if stderr_line:
                    stderr_lines.append(stderr_line)
                
                # Check if process has finished
                if process.poll() is not None:
                    # Read any remaining output
                    remaining_stdout, remaining_stderr = process.communicate()
                    if remaining_stdout:
                        stdout_lines.append(remaining_stdout)
                    if remaining_stderr:
                        stderr_lines.append(remaining_stderr)
                    break
            
            stdout = ''.join(stdout_lines)
            stderr = ''.join(stderr_lines)
            
            # Check output for common issues
            stderr_lower = stderr.lower() if stderr else ""
            stdout_lower = stdout.lower() if stdout else ""
            
            # Handle unregistered/evaluation mode - this is OK, just a warning
            if "evaluation" in stderr_lower or "unregistered" in stderr_lower:
                logger.warning("MakeMKV is running in evaluation mode (no beta key registered)")
                logger.info("Rip completed successfully in evaluation mode")
                return
            
            # Handle actual errors
            if process.returncode != 0:
                logger.error(f"Rip failed with exit code {process.returncode}")
                if stderr:
                    logger.error(f"stderr: {stderr}")
                raise RipError(f"Rip failed: {stderr or 'Unknown error'}")
            
            logger.info(f"Rip completed: {disc_info.name}")
            
        except FileNotFoundError:
            raise RipError("makemkvcon not found. Is MakeMKV installed?")
