"""Path utilities."""

import re
from pathlib import Path


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename.
    
    Args:
        name: The name to sanitize
        
    Returns:
        Sanitized filename
    """
    # Replace invalid characters with dash
    sanitized = re.sub(r'[\\/:*?"<>|]', '-', name)
    # Remove multiple consecutive dashes
    sanitized = re.sub(r'-+', '-', sanitized)
    # Remove leading/trailing dashes and spaces
    sanitized = sanitized.strip(' -')
    # Limit length
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    
    return sanitized


def ensure_dir(path: Path, mode: int = 0o755) -> Path:
    """Ensure a directory exists.
    
    Args:
        path: Directory path
        mode: Directory permissions
        
    Returns:
        The directory path
    """
    path.mkdir(parents=True, exist_ok=True, mode=mode)
    return path


def get_disk_usage(path: Path) -> dict:
    """Get disk usage information.
    
    Args:
        path: Path to check
        
    Returns:
        Dictionary with total, used, free bytes and percentage
    """
    import shutil
    
    usage = shutil.disk_usage(path)
    return {
        "total": usage.total,
        "used": usage.used,
        "free": usage.free,
        "percent_used": (usage.used / usage.total) * 100,
    }
