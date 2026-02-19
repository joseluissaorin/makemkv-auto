"""Disc monitoring daemon."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from makemkv_auto.config import Config
from makemkv_auto.logger import get_logger
from makemkv_auto.ripper import DiscAnalyzer, Ripper
from makemkv_auto.utils.notifications import notify
from makemkv_auto.web.state import StateManager

logger = get_logger(__name__)


class DiscMonitor:
    """Monitors optical drive for disc insertions."""
    
    def __init__(self, config: Config) -> None:
        self.config = config
        self.device = config.devices.primary
        self.check_interval = config.service.check_interval
        self.disc_inserted = False
        self.running = False
        self.lock_file = Path("/tmp/makemkv-auto-ripping.lock")
        self.state_manager = StateManager()
    
    def run(self) -> None:
        """Run the monitor loop."""
        logger.info(f"Starting disc monitor for {self.device}")
        logger.info(f"Check interval: {self.check_interval}s")
        
        self.running = True
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        try:
            while self.running:
                self._check_disc()
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            logger.info("Monitor stopped by user")
        finally:
            self.running = False
    
    def run_daemon(self) -> None:
        """Run as a daemon process."""
        try:
            import daemon
            import daemon.pidfile
        except ImportError:
            logger.error("python-daemon not installed. Cannot run as daemon.")
            raise RuntimeError("python-daemon package required for daemon mode")
        
        pidfile = daemon.pidfile.PIDLockFile("/var/run/makemkv-auto.pid")
        
        with daemon.DaemonContext(
            pidfile=pidfile,
            signal_map={
                signal.SIGTERM: self._signal_handler,
                signal.SIGINT: self._signal_handler,
            },
        ):
            self.run()
    
    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def _check_disc(self) -> None:
        """Check for disc and process if found."""
        # Check if drive exists
        if not Path(self.device).exists():
            return
        
        # Check if already ripping
        if self._is_ripping():
            return
        
        # Check for disc
        disc_present = self._is_disc_present()
        
        if disc_present and not self.disc_inserted:
            # New disc detected
            logger.info("New disc detected!")
            self.disc_inserted = True
            
            # Wait for drive to settle
            time.sleep(3)
            
            # Process disc
            self._process_disc()
            
        elif not disc_present and self.disc_inserted:
            # Disc removed
            logger.info("Disc removed")
            self.disc_inserted = False
    
    def _is_disc_present(self) -> bool:
        """Check if a disc is present."""
        try:
            result = subprocess.run(
                ["makemkvcon", "-r", "--cache=1", "info", f"dev:{self.device}"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            # Check for DRV lines with actual disc data (non-empty name field)
            for line in result.stdout.split('\n'):
                if line.startswith('DRV:'):
                    parts = line.split('","')
                    if len(parts) >= 3:
                        disc_name = parts[1].strip('"')
                        if disc_name:
                            return True
            return False
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _is_ripping(self) -> bool:
        """Check if a rip is currently in progress."""
        if not self.lock_file.exists():
            return False
        
        try:
            pid = int(self.lock_file.read_text().strip())
            # Check if process is still running
            os.kill(pid, 0)
            return True
        except (ValueError, OSError, ProcessLookupError):
            # Process not running, clean up stale lock
            self.lock_file.unlink(missing_ok=True)
            return False
    
    def _process_disc(self) -> None:
        """Process detected disc."""
        logger.info("Processing disc...")
        
        # Create lock file
        self.lock_file.write_text(str(os.getpid()))
        
        try:
            analyzer = DiscAnalyzer(self.config)
            ripper = Ripper(self.config)
            
            # Analyze disc
            disc_info = analyzer.get_disc_info()
            logger.info(f"Detected: {disc_info.name} ({disc_info.content_type.value})")
            
            # Update state - start ripping
            total_titles = len(disc_info.titles) if hasattr(disc_info, 'titles') else 1
            self.state_manager.start_rip(
                disc_name=disc_info.name,
                sanitized_name=disc_info.sanitized_name,
                content_type=disc_info.content_type.value if hasattr(disc_info.content_type, 'value') else str(disc_info.content_type),
                total_titles=total_titles,
                device=self.device
            )
            
            # Determine output path
            if disc_info.content_type.value == "tvshow":
                if self.config.paths.tv_shows is None:
                    raise RuntimeError("TV shows path not configured")
                output_path = self.config.paths.tv_shows / disc_info.sanitized_name
            else:
                if self.config.paths.movies is None:
                    raise RuntimeError("Movies path not configured")
                output_path = self.config.paths.movies / disc_info.sanitized_name
            
            # Check if already ripped
            if output_path.exists() and any(output_path.iterdir()):
                if not self.config.detection.overwrite_existing:
                    logger.info(f"Already ripped: {output_path}")
                    notify(f"Disc already ripped: {disc_info.name}")
                    self.state_manager.complete_rip(str(output_path), 0, 0)
                    
                    if self.config.detection.auto_eject:
                        subprocess.run(["eject", self.device])
                    return
            
            # Rip disc
            logger.info(f"Ripping to: {output_path}")
            notify(f"Starting rip: {disc_info.name}")
            
            try:
                ripper.rip_disc(disc_info, output_path, state_manager=self.state_manager)
                logger.info(f"Rip completed: {disc_info.name}")
                notify(f"Rip completed: {disc_info.name}")
                
                # Count files and size
                file_count = 0
                total_size = 0
                for root, dirs, files in os.walk(output_path):
                    for file in files:
                        if file.endswith('.mkv'):
                            file_count += 1
                            total_size += os.path.getsize(os.path.join(root, file))
                
                # Update state - complete
                self.state_manager.complete_rip(
                    str(output_path),
                    file_count=file_count,
                    total_size_mb=total_size / (1024 * 1024)
                )
                
                if self.config.detection.auto_eject:
                    subprocess.run(["eject", self.device])
                    
            except Exception as e:
                logger.error(f"Rip failed: {e}")
                notify(f"Rip failed: {disc_info.name}", urgency="critical")
                self.state_manager.set_error(str(e))
        
        except Exception as e:
            logger.error(f"Error processing disc: {e}")
            self.state_manager.set_error(str(e))
        
        finally:
            # Remove lock file
            self.lock_file.unlink(missing_ok=True)
