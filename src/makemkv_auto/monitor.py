"""Disc monitoring daemon."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from makemkv_auto.config import Config
from makemkv_auto.disc_db import DiscDatabase
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
        self.disc_db = DiscDatabase()
    
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
        logger.debug(f"_check_disc() called - checking device {self.device}")
        
        # Check if drive exists
        if not Path(self.device).exists():
            logger.debug(f"Device {self.device} does not exist, skipping check")
            return
        logger.debug(f"Device {self.device} exists")
        
        # Check if already ripping
        if self._is_ripping():
            logger.debug("Already ripping, skipping check")
            return
        logger.debug("Not currently ripping")
        
        # Check for disc
        logger.debug(f"Calling _is_disc_present() for {self.device}")
        disc_present = self._is_disc_present()
        logger.debug(f"_is_disc_present() returned: {disc_present}")
        logger.debug(f"Current disc_inserted state: {self.disc_inserted}")
        
        if disc_present and not self.disc_inserted:
            # New disc detected
            logger.info("*** NEW DISC DETECTED! ***")
            logger.info(f"Disc inserted state was: {self.disc_inserted}, changing to True")
            self.disc_inserted = True
            
            # Wait for drive to settle
            logger.info("Waiting 3 seconds for drive to settle...")
            time.sleep(3)
            
            # Process disc
            logger.info("Starting _process_disc()")
            self._process_disc()
            logger.info("_process_disc() completed")
            
        elif not disc_present and self.disc_inserted:
            # Disc removed
            logger.info("Disc removed")
            self.disc_inserted = False
    
    def _is_disc_present(self) -> bool:
        """Check if a disc is present."""
        logger.debug(f"_is_disc_present() called for device {self.device}")
        try:
            logger.debug(f"Running makemkvcon info command for {self.device}")
            result = subprocess.run(
                ["makemkvcon", "-r", "--cache=1", "info", f"dev:{self.device}"],
                capture_output=True,
                text=True,
                timeout=300,
            )
            logger.debug(f"makemkvcon completed with return code: {result.returncode}")
            logger.debug(f"makemkvcon stdout length: {len(result.stdout)} chars")
            logger.debug(f"makemkvcon stderr length: {len(result.stderr)} chars")
            
            # Check for DRV lines with actual disc data (non-empty name field)
            drv_lines = [line for line in result.stdout.split('\n') if line.startswith('DRV:')]
            logger.debug(f"Found {len(drv_lines)} DRV lines")
            
            for i, line in enumerate(drv_lines):
                logger.debug(f"Processing DRV line {i}: {line[:100]}...")
                parts = line.split('","')
                logger.debug(f"  Split into {len(parts)} parts")
                if len(parts) >= 3:
                    disc_name = parts[1].strip('"')
                    logger.debug(f"  Disc name: '{disc_name}'")
                    if disc_name:
                        logger.info(f"*** DISC PRESENT: '{disc_name}' ***")
                        return True
            
            logger.debug("No disc found in any DRV line")
            return False
        except subprocess.TimeoutExpired as e:
            logger.error(f"TIMEOUT: makemkvcon timed out after 60s: {e}")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"CALLEDPROCESSERROR: makemkvcon failed: {e}")
            return False
        except FileNotFoundError as e:
            logger.error(f"FILENOTFOUND: makemkvcon not found: {e}")
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
    
    def _get_folder_duration(self, folder: Path) -> int:
        """Get total duration of all MKV files in folder (in seconds)."""
        total_duration = 0
        try:
            for mkv_file in folder.glob("*.mkv"):
                # Use ffprobe to get duration if available, otherwise estimate from file size
                try:
                    result = subprocess.run(
                        ["ffprobe", "-v", "error", "-show_entries", "format=duration", 
                         "-of", "default=noprint_wrappers=1:nokey=1", str(mkv_file)],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0:
                        total_duration += int(float(result.stdout.strip()))
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    # ffprobe not available, estimate from file size (rough approximation)
                    # Assume ~1GB per hour for Blu-ray quality
                    file_size_gb = mkv_file.stat().st_size / (1024**3)
                    estimated_duration = int(file_size_gb * 3600)  # 1GB ≈ 1 hour
                    total_duration += estimated_duration
        except Exception as e:
            logger.warning(f"Could not calculate folder duration: {e}")
        return total_duration
    
    def _process_disc(self) -> None:
        """Process detected disc."""
        logger.info("="*60)
        logger.info("PROCESS_DISC STARTED")
        logger.info("="*60)
        
        # Create lock file
        logger.info(f"Creating lock file: {self.lock_file}")
        self.lock_file.write_text(str(os.getpid()))
        logger.info(f"Lock file created with PID: {os.getpid()}")
        
        try:
            logger.info("Creating DiscAnalyzer...")
            analyzer = DiscAnalyzer(self.config)
            logger.info("DiscAnalyzer created successfully")
            
            logger.info("Creating Ripper...")
            ripper = Ripper(self.config)
            logger.info("Ripper created successfully")
            
            # Analyze disc
            logger.info("Calling analyzer.get_disc_info()...")
            disc_info = analyzer.get_disc_info()
            logger.info(f"*** ANALYSIS COMPLETE ***")
            logger.info(f"Disc name: {disc_info.name}")
            logger.info(f"Sanitized name: {disc_info.sanitized_name}")
            logger.info(f"Content type: {disc_info.content_type}")
            logger.info(f"Confidence: {disc_info.confidence}")
            logger.info(f"Number of titles: {len(disc_info.titles)}")
            logger.info(f"Detected: {disc_info.name} ({disc_info.content_type.value})")
            
            # Update state - start ripping
            total_titles = len(disc_info.titles) if hasattr(disc_info, 'titles') else 1
            logger.info(f"Total titles to rip: {total_titles}")
            
            logger.info("Calling state_manager.start_rip()...")
            self.state_manager.start_rip(
                disc_name=disc_info.name,
                sanitized_name=disc_info.sanitized_name,
                content_type=disc_info.content_type.value if hasattr(disc_info.content_type, 'value') else str(disc_info.content_type),
                total_titles=total_titles,
                device=self.device
            )
            logger.info("State updated to 'ripping'")
            
            # Determine output path
            if disc_info.content_type.value == "tvshow":
                if self.config.paths.tv_shows is None:
                    raise RuntimeError("TV shows path not configured")
                base_output_path = self.config.paths.tv_shows / disc_info.sanitized_name
            else:
                if self.config.paths.movies is None:
                    raise RuntimeError("Movies path not configured")
                base_output_path = self.config.paths.movies / disc_info.sanitized_name
            
            # Check for duplicate or multi-disc scenario
            output_path = base_output_path
            disc_already_ripped = False
            existing_path = None
            
            # Check if folder exists and has content
            if base_output_path.exists() and any(base_output_path.iterdir()):
                if not self.config.detection.overwrite_existing:
                    
                    # STRATEGY 1: Check unique disc ID (most reliable)
                    if disc_info.disc_id and self.disc_db.has_disc(disc_info.disc_id):
                        existing_disc = self.disc_db.get_disc(disc_info.disc_id)
                        existing_path = existing_disc.get("output_path") if existing_disc else None
                        logger.info(f"Duplicate disc detected by ID: {disc_info.disc_id[:30]}...")
                        logger.info(f"Previously ripped to: {existing_path}")
                        disc_already_ripped = True
                    
                    # STRATEGY 2: For TV shows - ALWAYS auto-number (never skip based on duration)
                    # TV series discs always get numbered folders
                    elif disc_info.content_type.value == "tvshow":
                        logger.info(f"TV show detected - auto-numbering folders")
                        disc_number = 1
                        parent_dir = base_output_path.parent
                        base_name = base_output_path.name
                        
                        # If base folder exists, start from Disc 2
                        if base_output_path.exists() and any(base_output_path.iterdir()):
                            disc_number = 2
                        
                        while True:
                            if disc_number == 1:
                                new_name = base_name
                            else:
                                new_name = f"{base_name} Disc {disc_number}"
                            
                            output_path = parent_dir / new_name
                            if not output_path.exists() or not any(output_path.iterdir()):
                                if disc_number > 1:
                                    logger.info(f"TV series: using '{new_name}'")
                                break
                            disc_number += 1
                            
                            # Safety limit
                            if disc_number > 20:
                                logger.warning("Too many discs detected")
                                output_path = base_output_path
                                break
                    
                    # STRATEGY 3: For movies - use duration comparison
                    else:
                        existing_titles = sum(1 for f in base_output_path.glob("*.mkv"))
                        existing_duration = self._get_folder_duration(base_output_path)
                        new_total_duration = sum(t.duration for t in disc_info.titles)
                        
                        logger.info(f"Movie check: {existing_titles} files @ {existing_duration//60}min vs {len(disc_info.titles)} titles @ {new_total_duration//60}min")
                        
                        # If title count and duration are very similar, it's likely the same disc
                        duration_diff_pct = abs(existing_duration - new_total_duration) / max(new_total_duration, 1) * 100
                        titles_match = abs(existing_titles - len(disc_info.titles)) <= 1
                        
                        if titles_match and duration_diff_pct < 5:
                            logger.info(f"Same movie detected (duration diff: {duration_diff_pct:.1f}%) - skipping")
                            disc_already_ripped = True
                            existing_path = str(base_output_path)
                        else:
                            # Different movie - find next available number
                            logger.info(f"Different movie detected - auto-numbering")
                            disc_number = 2
                            parent_dir = base_output_path.parent
                            base_name = base_output_path.name
                            
                            while True:
                                new_name = f"{base_name} ({disc_number})"
                                output_path = parent_dir / new_name
                                if not output_path.exists() or not any(output_path.iterdir()):
                                    logger.info(f"Using alternate folder: '{new_name}'")
                                    break
                                disc_number += 1
                                
                                if disc_number > 20:
                                    logger.warning("Too many versions detected")
                                    output_path = base_output_path
                                    break
            
            # Handle already-ripped disc
            if disc_already_ripped:
                logger.info(f"Disc already ripped: {existing_path}")
                notify(f"Disc already ripped: {disc_info.name}")
                self.state_manager.complete_rip(existing_path or str(base_output_path), 0, 0)
                
                if self.config.detection.auto_eject:
                    subprocess.run(["eject", self.device])
                return
            
            # Rip disc
            logger.info(f"Starting rip process...")
            logger.info(f"Output path: {output_path}")
            notify(f"Starting rip: {disc_info.name}")
            
            try:
                logger.info("Calling ripper.rip_disc()...")
                ripper.rip_disc(disc_info, output_path, state_manager=self.state_manager)
                logger.info(f"*** RIP COMPLETED SUCCESSFULLY ***")
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
                
                # Add to disc database for duplicate detection
                if disc_info.disc_id:
                    self.disc_db.add_disc(
                        disc_id=disc_info.disc_id,
                        disc_name=disc_info.name,
                        output_path=str(output_path)
                    )
                else:
                    logger.warning(f"No disc ID available for {disc_info.name} - won't be tracked for duplicates")
                
                if self.config.detection.auto_eject:
                    subprocess.run(["eject", self.device])
                    
            except Exception as e:
                logger.error(f"Rip failed: {e}")
                notify(f"Rip failed: {disc_info.name}", urgency="critical")
                self.state_manager.set_error(str(e))
        
        except Exception as e:
            logger.error("="*60)
            logger.error(f"CRITICAL ERROR IN _process_disc: {type(e).__name__}: {e}")
            logger.error("="*60)
            import traceback
            logger.error(f"TRACEBACK:\n{traceback.format_exc()}")
            self.state_manager.set_error(str(e))
            logger.error("Error state saved")
        
        finally:
            # Remove lock file
            self.lock_file.unlink(missing_ok=True)
