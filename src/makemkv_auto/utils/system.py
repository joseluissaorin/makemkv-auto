"""System utilities."""

import os
import subprocess
from pathlib import Path


def is_root() -> bool:
    """Check if running as root."""
    return os.geteuid() == 0


def get_username() -> str:
    """Get the current username."""
    import getpass
    return getpass.getuser()


def run_command(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int | None = None,
    capture_output: bool = True,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run a shell command.
    
    Args:
        cmd: Command and arguments
        cwd: Working directory
        timeout: Timeout in seconds
        capture_output: Whether to capture stdout/stderr
        check: Whether to raise on non-zero exit
        
    Returns:
        CompletedProcess instance
    """
    return subprocess.run(
        cmd,
        cwd=cwd,
        timeout=timeout,
        capture_output=capture_output,
        text=True,
        check=check,
    )


def command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    import shutil
    return shutil.which(cmd) is not None
