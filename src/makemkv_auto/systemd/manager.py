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
    
    def __init__(self, user: bool = False) -> None:
        self.user = user
        
        if user:
            self.system_dir = Path.home() / ".config" / "systemd" / "user"
            self.config_path = Path.home() / ".config" / "makemkv-auto" / "config.yaml"
            self.target = "default.target"
        else:
            self.system_dir = Path("/etc/systemd/system")
            self.config_path = Path("/etc/makemkv-auto/config.yaml")
            self.target = "multi-user.target"
    
    def _get_python_path(self) -> str:
        """Get the Python executable path that has makemkv_auto installed."""
        import sys
        
        # First, try the current Python (the one running this code)
        current_python = sys.executable
        if current_python and self._check_python_has_module(current_python):
            return current_python
        
        # Try common Python versions
        for py_cmd in ["python3.11", "python3.12", "python3.13", "python3", "python"]:
            py_path = shutil.which(py_cmd)
            if py_path and self._check_python_has_module(py_path):
                return py_path
        
        # Fallback to system Python
        return shutil.which("python3") or shutil.which("python") or "/usr/bin/python3"
    
    def _check_python_has_module(self, python_path: str) -> bool:
        """Check if the given Python has makemkv_auto installed."""
        try:
            result = subprocess.run(
                [python_path, "-c", "import makemkv_auto; print('OK')"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0 and "OK" in result.stdout
        except Exception:
            return False
    
    def _get_monitor_service_template(self) -> str:
        """Generate monitor service template based on user/system mode."""
        user_group_lines = ""
        if not self.user:
            user_group_lines = """User=root
Group=cdrom
"""
        
        return f"""[Unit]
Description=MakeMKV Auto Monitor - Disc insertion detection
After=local-fs.target network.target

[Service]
Type=simple
{user_group_lines}Environment="PYTHONUNBUFFERED=1"
Environment="MKA_CONFIG={self.config_path}"
ExecStart={self._get_python_path()} -m makemkv_auto monitor
ExecReload=/bin/kill -HUP $MAINPID
KillMode=mixed
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy={self.target}
"""
    
    def _get_web_service_template(self) -> str:
        """Generate web service template based on user/system mode."""
        user_line = ""
        if not self.user:
            user_line = "User=root\n"
        
        return f"""[Unit]
Description=MakeMKV Auto Web UI
After=network.target
Wants=makemkv-auto-monitor.service

[Service]
Type=simple
{user_line}Environment="MKA_CONFIG={self.config_path}"
ExecStart={self._get_python_path()} -m uvicorn makemkv_auto.web.app:app --host 0.0.0.0 --port 8766 --log-level info
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy={self.target}
"""
    
    def _get_timer_template(self) -> str:
        """Generate timer template."""
        return f"""[Unit]
Description=MakeMKV Beta Key Update Timer

[Timer]
OnCalendar=monthly
Persistent=true

[Install]
WantedBy=timers.target
"""
    
    def install_services(self) -> None:
        """Install systemd service files."""
        logger.info("Installing systemd services...")
        
        # Create systemd directory if needed
        self.system_dir.mkdir(parents=True, exist_ok=True)
        
        # Install monitor service
        service_content = self._get_monitor_service_template()
        service_path = self.system_dir / SYSTEMD_SERVICE_NAME
        service_path.write_text(service_content)
        
        # Install timer
        timer_content = self._get_timer_template()
        timer_path = self.system_dir / SYSTEMD_TIMER_NAME
        timer_path.write_text(timer_content)
        
        # Install web service
        web_content = self._get_web_service_template()
        web_service_path = self.system_dir / "makemkv-auto-web.service"
        web_service_path.write_text(web_content)
        
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
            cmd = ["systemctl"]
            if self.user:
                cmd.append("--user")
            cmd.extend(["status", SYSTEMD_SERVICE_NAME])
            
            result = subprocess.run(
                cmd,
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
        cmd = ["journalctl"]
        
        if self.user:
            cmd.append("--user")
        
        cmd.extend(["-u", SYSTEMD_SERVICE_NAME, "-n", str(lines)])
        
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
