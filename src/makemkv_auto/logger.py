"""Logging configuration with structlog and standard library."""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from rich.console import Console
from rich.logging import RichHandler

from makemkv_auto.config import LoggingConfig

console = Console()

# Track if we've shown warnings to avoid spamming
_shown_warnings: set[str] = set()


def _show_warning_once(message: str, style: str = "yellow") -> None:
    """Show a warning only once per session."""
    if message not in _shown_warnings:
        _shown_warnings.add(message)
        console.print(f"[{style}]{message}[/{style}]")


def setup_logging(config: LoggingConfig, log_file: Path | None = None) -> None:
    """Configure logging with both structlog and standard library."""
    
    # Parse max size
    max_bytes = parse_size(config.max_size)
    
    # Configure standard library logging
    handlers: list[logging.Handler] = []
    
    # Rich handler for console output
    rich_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
    )
    rich_handler.setLevel(getattr(logging, config.level.upper()))
    handlers.append(rich_handler)
    
    # File handler if log file specified
    if log_file:
        try:
            # Try to create the log directory and file
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Test if we can write to the directory
            test_file = log_file.parent / ".write_test"
            test_file.touch()
            test_file.unlink()
            
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=config.retention_days,
            )
            file_handler.setLevel(logging.DEBUG)
            handlers.append(file_handler)
        except (PermissionError, OSError):
            # Fall back to user log directory
            user_log_dir = Path.home() / ".local" / "share" / "makemkv-auto" / "logs"
            try:
                user_log_dir.mkdir(parents=True, exist_ok=True)
                user_log_file = user_log_dir / log_file.name
                
                from logging.handlers import RotatingFileHandler
                file_handler = RotatingFileHandler(
                    user_log_file,
                    maxBytes=max_bytes,
                    backupCount=config.retention_days,
                )
                file_handler.setLevel(logging.DEBUG)
                handlers.append(file_handler)
                _show_warning_once(f"Warning: Cannot write to {log_file.parent}. Using {user_log_dir} instead.", style="dim yellow")
            except (PermissionError, OSError):
                # Can't write anywhere, skip file logging
                _show_warning_once("Warning: Cannot write to log file. Logging to console only.", style="dim yellow")
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, config.level.upper()),
        format="%(message)s",
        datefmt="[%X]",
        handlers=handlers,
    )
    
    # Configure structlog
    shared_processors: list[Any] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if config.structured:
        # Structured logging (JSON)
        structlog.configure(
            processors=shared_processors + [
                structlog.processors.JSONRenderer(serializer=json.dumps),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    else:
        # Pretty console logging
        structlog.configure(
            processors=shared_processors + [
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )


def parse_size(size_str: str) -> int:
    """Parse size string like '100MB' to bytes."""
    size_str = size_str.strip().upper()
    
    # Check for multi-character units first (order matters!)
    units = [
        ("GB", 1024 ** 3),
        ("MB", 1024 ** 2),
        ("KB", 1024),
        ("B", 1),
    ]
    
    for unit, multiplier in units:
        if size_str.endswith(unit):
            number = size_str[:-len(unit)].strip()
            try:
                return int(float(number) * multiplier)
            except ValueError:
                raise ValueError(f"Invalid size format: {size_str}")
    
    # Assume bytes if no unit
    try:
        return int(size_str)
    except ValueError:
        raise ValueError(f"Invalid size format: {size_str}")


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger."""
    return structlog.get_logger(name)
