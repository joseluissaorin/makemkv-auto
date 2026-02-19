"""Custom exceptions for makemkv-auto."""


class MakeMKVAutoError(Exception):
    """Base exception for makemkv-auto."""
    
    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


class ConfigurationError(MakeMKVAutoError):
    """Configuration-related errors."""
    pass


class MakeMKVNotInstalledError(MakeMKVAutoError):
    """MakeMKV is not installed."""
    pass


class DiscError(MakeMKVAutoError):
    """Disc-related errors."""
    pass


class NoDiscError(DiscError):
    """No disc detected in drive."""
    pass


class RipError(MakeMKVAutoError):
    """Ripping operation failed."""
    pass


class ServiceError(MakeMKVAutoError):
    """Systemd service operation failed."""
    pass


class BetaKeyError(MakeMKVAutoError):
    """Beta key operation failed."""
    pass
