"""Systemd service management."""

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from makemkv_auto.constants import (
    APP_NAME,
    SYSTEMD_SERVICE_NAME,
    SYSTEMD_TIMER_NAME,
)
from makemkv_auto.logger import get_logger

logger = get_logger(__name__)


class SystemdManager:
    """Manages systemd service files and operations."""
    
    SERVICE_TEMPLATE = """[Unit]
Description=MakeMKV Auto Monitor - Disc insertion detection
After=local-fs.target network.target

[Service]
Type=simple
User=root
Group=cdrom
Environment="PYTHONUNBUFFERED=1"
Environment="MKA_CONFIG=/etc/makemkv-auto/config.yaml"
ExecStart={python_path} -m makemkv_auto monitor
ExecReload=/bin/kill -HUP $MAINPID
KillMode=mixed
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

    TIMER_TEMPLATE = """[Unit]
Description=MakeMKV Beta Key Update Timer

[Timer]
OnCalendar=monthly
Persistent=true

[Install]
WantedBy=timers.target
"""

    def __init__(self, user: bool = False) -> None:
        self.user = user
        
        if user:
            self.system_dir = Path.home() / ".config" / "systemd" / "user"
        else:
            self.system_dir = Path("/etc/systemd/system")
    
    def _get_python_path(self) -> str:
        """Get the Python executable path."""
        return shutil.which("python3") or shutil.which("python") or "/usr/bin/python3"
    
    WEB_SERVICE_TEMPLATE = """[Unit]
Description=MakeMKV Auto Web UI
After=network.target
Wants=makemkv-auto-monitor.service

[Service]
Type=simple
User=root
Environment="MKA_CONFIG=/etc/makemkv-auto/config.yaml"
ExecStart=/usr/bin/python3.11 -m uvicorn makemkv_auto.web.app:app --host 0.0.0.0 --port 8766 --log-level info
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

    def install_services(self) -> None:
        """Install systemd service files."""
        logger.info("Installing systemd services...")
        
        # Create systemd directory if needed
        self.system_dir.mkdir(parents=True, exist_ok=True)
        
        # Install monitor service
        service_content = self.SERVICE_TEMPLATE.format(
            python_path=self._get_python_path(),
        )
        
        service_path = self.system_dir / SYSTEMD_SERVICE_NAME
        service_path.write_text(service_content)
        
        # Install timer
        timer_path = self.system_dir / SYSTEMD_TIMER_NAME
        timer_path.write_text(self.TIMER_TEMPLATE)
        
        # Install web service
        web_service_path = self.system_dir / "makemkv-auto-web.service"
        web_service_path.write_text(self.WEB_SERVICE_TEMPLATE)
        
        # Reload systemd
        self._daemon_reload()
        
        logger.info("Systemd services installed")
    
    def uninstall_services(self, force: bool = False) -> None:
        """Remove systemd service files."""
        logger.info("Uninstalling systemd services...")
        
        # Stop and disable if running
        try:
            self.stop()
            self.disable()
        except Exception:
            if not force:
                raise
        
        # Remove service files
        service_path = self.system_dir / SYSTEMD_SERVICE_NAME
        timer_path = self.system_dir / SYSTEMD_TIMER_NAME
        web_service_path = self.system_dir / "makemkv-auto-web.service"
        
        if service_path.exists():
            service_path.unlink()
        
        if timer_path.exists():
            timer_path.unlink()
            
        if web_service_path.exists():
            web_service_path.unlink()
        
        # Reload systemd
        self._daemon_reload()
        
        logger.info("Systemd services uninstalled")
    
    def enable(self) -> None:
        """Enable services to start on boot."""
        logger.info("Enabling services...")
        self._run_systemctl("enable", SYSTEMD_SERVICE_NAME)
        self._run_systemctl("enable", SYSTEMD_TIMER_NAME)
    
    def disable(self) -> None:
        """Disable services from starting on boot."""
        logger.info("Disabling services...")
        self._run_systemctl("disable", SYSTEMD_SERVICE_NAME, check=False)
        self._run_systemctl("disable", SYSTEMD_TIMER_NAME, check=False)
    
    def start(self) -> None:
        """Start services."""
        logger.info("Starting services...")
        self._run_systemctl("start", SYSTEMD_SERVICE_NAME)
    
    def stop(self) -> None:
        """Stop services."""
        logger.info("Stopping services...")
        self._run_systemctl("stop", SYSTEMD_SERVICE_NAME, check=False)
    
    def restart(self) -> None:
        """Restart services."""
        logger.info("Restarting services...")
        self._run_systemctl("restart", SYSTEMD_SERVICE_NAME)
    
    def status(self) -> dict:
        """Get service status."""
        service_path = self.system_dir / SYSTEMD_SERVICE_NAME
        
        if not service_path.exists():
            return {"installed": False}
        
        try:
            result = subprocess.run(
                ["systemctl", "--user" if self.user else "", "status", SYSTEMD_SERVICE_NAME],
                capture_output=True,
                text=True,
            )
            
            output = result.stdout + result.stderr
            
            # Parse status
            state = "unknown"
            enabled = False
            pid = None
            
            if "Active: active (running)" in output:
                state = "running"
            elif "Active: inactive" in output:
                state = "stopped"
            elif "Active: failed" in output:
                state = "failed"
            
            if "Loaded: loaded" in output and "enabled" in output:
                enabled = True
            
            # Extract PID
            import re
            pid_match = re.search(r"Main PID: (\d+)", output)
            if pid_match:
                pid = int(pid_match.group(1))
            
            return {
                "installed": True,
                "state": state,
                "enabled": enabled,
                "pid": pid,
            }
        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return {"installed": True, "state": "unknown", "enabled": False}
    
    def logs(self, follow: bool = False, lines: int = 50) -> str:
        """Get service logs."""
        cmd = [
            "journalctl",
            "--user" if self.user else "",
            "-u", SYSTEMD_SERVICE_NAME,
            "-n", str(lines),
        ]
        
        if follow:
            cmd.append("-f")
            subprocess.run(cmd)
            return ""
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        return result.stdout
    
    def _run_systemctl(self, action: str, unit: str, check: bool = True) -> None:
        """Run a systemctl command."""
        cmd = ["systemctl"]
        
        if self.user:
            cmd.append("--user")
        
        cmd.extend([action, unit])
        
        subprocess.run(cmd, check=check)
    
    def _daemon_reload(self) -> None:
        """Reload systemd daemon."""
        cmd = ["systemctl"]
        
        if self.user:
            cmd.append("--user")
        
        cmd.append("daemon-reload")
        
        subprocess.run(cmd, check=True)
