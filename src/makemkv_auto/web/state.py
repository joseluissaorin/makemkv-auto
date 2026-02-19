"""Shared state management for web UI and monitor service."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from makemkv_auto.logger import get_logger

logger = get_logger(__name__)

DEFAULT_STATE_FILE = Path("/tmp/makemkv-auto-state.json")


class ServiceStatus(str, Enum):
    """Service status states."""
    IDLE = "idle"
    RIPPING = "ripping"
    ERROR = "error"
    STARTING = "starting"


@dataclass
class LastRipInfo:
    """Information about the last completed rip."""
    name: str
    completed_at: str
    output_path: str
    file_count: int = 0
    total_size_mb: float = 0.0


@dataclass
class ServiceState:
    """Shared state between monitor and web UI."""
    status: ServiceStatus = ServiceStatus.IDLE
    disc_name: Optional[str] = None
    sanitized_name: Optional[str] = None
    content_type: Optional[str] = None
    progress_percent: float = 0.0
    current_title: int = 0
    total_titles: int = 0
    start_time: Optional[str] = None
    eta_seconds: Optional[int] = None
    error_message: Optional[str] = None
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    last_rip: Optional[LastRipInfo] = None
    device: str = "/dev/sr0"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary."""
        data = asdict(self)
        # Convert enum to string
        data["status"] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ServiceState:
        """Create state from dictionary."""
        # Convert string back to enum
        if "status" in data and isinstance(data["status"], str):
            data["status"] = ServiceStatus(data["status"])
        
        # Handle LastRipInfo nested object
        if data.get("last_rip") and isinstance(data["last_rip"], dict):
            data["last_rip"] = LastRipInfo(**data["last_rip"])
        
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def save(self, filepath: Path = DEFAULT_STATE_FILE) -> None:
        """Save state to JSON file."""
        try:
            self.last_updated = datetime.now().isoformat()
            filepath.write_text(json.dumps(self.to_dict(), indent=2))
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    @classmethod
    def load(cls, filepath: Path = DEFAULT_STATE_FILE) -> ServiceState:
        """Load state from JSON file."""
        try:
            if filepath.exists():
                data = json.loads(filepath.read_text())
                return cls.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
        
        return cls()  # Return default state if file doesn't exist or is corrupted
    
    def update(self, **kwargs) -> None:
        """Update state fields and save."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.save()
    
    def format_duration(self) -> str:
        """Format the duration since start time."""
        if not self.start_time:
            return "N/A"
        
        try:
            start = datetime.fromisoformat(self.start_time)
            duration = datetime.now() - start
            hours, remainder = divmod(int(duration.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            else:
                return f"{minutes}m {seconds}s"
        except Exception:
            return "N/A"
    
    def format_eta(self) -> str:
        """Format ETA."""
        if self.eta_seconds is None:
            return "Calculating..."
        
        if self.eta_seconds < 60:
            return f"{self.eta_seconds}s"
        elif self.eta_seconds < 3600:
            return f"{self.eta_seconds // 60}m"
        else:
            hours = self.eta_seconds // 3600
            minutes = (self.eta_seconds % 3600) // 60
            return f"{hours}h {minutes}m"


class StateManager:
    """Manager for service state with automatic file synchronization."""
    
    def __init__(self, filepath: Path = DEFAULT_STATE_FILE):
        self.filepath = filepath
        self._state = ServiceState.load(filepath)
    
    @property
    def state(self) -> ServiceState:
        """Get current state (reloads from file to get updates from other processes)."""
        self._state = ServiceState.load(self.filepath)
        return self._state
    
    def update(self, **kwargs) -> None:
        """Update state and save to file."""
        self._state.update(**kwargs)
    
    def start_rip(self, disc_name: str, sanitized_name: str, content_type: str, total_titles: int, device: str) -> None:
        """Mark the start of a rip operation."""
        self.update(
            status=ServiceStatus.RIPPING,
            disc_name=disc_name,
            sanitized_name=sanitized_name,
            content_type=content_type,
            total_titles=total_titles,
            current_title=0,
            progress_percent=0.0,
            start_time=datetime.now().isoformat(),
            eta_seconds=None,
            error_message=None,
            device=device,
        )
        logger.info(f"State updated: started ripping {disc_name}")
    
    def update_progress(self, current_title: int, progress_percent: float, eta_seconds: Optional[int] = None) -> None:
        """Update rip progress."""
        self.update(
            current_title=current_title,
            progress_percent=progress_percent,
            eta_seconds=eta_seconds,
        )
    
    def complete_rip(self, output_path: str, file_count: int = 0, total_size_mb: float = 0.0) -> None:
        """Mark rip as completed."""
        last_rip = LastRipInfo(
            name=self._state.disc_name or "Unknown",
            completed_at=datetime.now().isoformat(),
            output_path=output_path,
            file_count=file_count,
            total_size_mb=total_size_mb,
        )
        
        self.update(
            status=ServiceStatus.IDLE,
            last_rip=last_rip,
            progress_percent=100.0,
            eta_seconds=None,
        )
        logger.info(f"State updated: completed rip of {last_rip.name}")
    
    def set_error(self, error_message: str) -> None:
        """Set error state."""
        self.update(
            status=ServiceStatus.ERROR,
            error_message=error_message,
        )
        logger.error(f"State updated: error - {error_message}")
    
    def clear_error(self) -> None:
        """Clear error state and return to idle."""
        self.update(
            status=ServiceStatus.IDLE,
            error_message=None,
        )
    
    def is_ripping(self) -> bool:
        """Check if currently ripping."""
        return self.state.status == ServiceStatus.RIPPING
