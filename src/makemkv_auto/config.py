"""Configuration management using Pydantic Settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from makemkv_auto.constants import (
    DEFAULT_CHECK_INTERVAL,
    DEFAULT_DEVICE,
    DEFAULT_LOG_DIR,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOG_MAX_SIZE,
    DEFAULT_LOG_RETENTION_DAYS,
    DEFAULT_MAX_EPISODE_DURATION,
    DEFAULT_MIN_EPISODE_DURATION,
    DEFAULT_MIN_MOVIE_DURATION,
    DEFAULT_MIN_LENGTH,
    DEFAULT_NAMING_PATTERN,
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_DELAY,
    DEFAULT_TEMP_DIR,
    MAKEMKV_DEFAULT_VERSION,
)


class MakeMKVConfig(BaseModel):
    """MakeMKV-specific configuration."""
    
    version: str = MAKEMKV_DEFAULT_VERSION
    install_path: Path = Path("/usr/local")
    beta_key: str | None = None


class PathsConfig(BaseModel):
    """Path configuration."""
    
    base: Path = Path("/media/joseluis/DATOS_HDD/datos_samba")
    movies: Path | None = None
    tv_shows: Path | None = None
    temp: Path = DEFAULT_TEMP_DIR
    logs: Path = DEFAULT_LOG_DIR
    
    def model_post_init(self, __context: Any) -> None:
        """Set default movie and TV show paths based on base path after initialization."""
        if self.movies is None and self.base is not None:
            object.__setattr__(self, 'movies', self.base / "Películas")
        if self.tv_shows is None and self.base is not None:
            object.__setattr__(self, 'tv_shows', self.base / "Series")


class DeviceConfig(BaseModel):
    """Device configuration."""
    
    primary: str = DEFAULT_DEVICE
    additional: list[str] = Field(default_factory=list)


class DetectionConfig(BaseModel):
    """Content detection configuration."""

    min_episode_duration: int = DEFAULT_MIN_EPISODE_DURATION  # minutes
    max_episode_duration: int = DEFAULT_MAX_EPISODE_DURATION  # minutes
    min_movie_duration: int = DEFAULT_MIN_MOVIE_DURATION  # minutes
    auto_eject: bool = True
    overwrite_existing: bool = False
    forced_types: dict[str, str] = Field(default_factory=dict)
    """Manual overrides for content type detection.
    
    Format: {"disc_name": "tvshow"} or {"disc_name": "movie"}
    Example: {"MISS MARPLE": "tvshow", "RANDOM MOVIE": "movie"}
    """


class OutputConfig(BaseModel):
    """Output configuration."""
    
    naming_pattern: str = DEFAULT_NAMING_PATTERN
    create_nfo: bool = False
    min_length: int = DEFAULT_MIN_LENGTH  # seconds


class LoggingConfig(BaseModel):
    """Logging configuration."""
    
    level: str = DEFAULT_LOG_LEVEL
    max_size: str = DEFAULT_LOG_MAX_SIZE
    retention_days: int = DEFAULT_LOG_RETENTION_DAYS
    structured: bool = False


class ServiceConfig(BaseModel):
    """Service configuration."""
    
    check_interval: int = DEFAULT_CHECK_INTERVAL  # seconds
    retry_count: int = DEFAULT_RETRY_COUNT
    retry_delay: int = DEFAULT_RETRY_DELAY  # seconds


class WebAuthConfig(BaseModel):
    """Web UI authentication configuration."""
    
    enabled: bool = False
    username: str = "admin"
    password: str = "changeme"


class WebConfig(BaseModel):
    """Web UI configuration."""
    
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8766
    auto_refresh: int = 5  # seconds
    log_lines: int = 100
    auth: WebAuthConfig = Field(default_factory=WebAuthConfig)


class Config(BaseSettings):
    """Main configuration class."""
    
    model_config = SettingsConfigDict(
        env_prefix="MKA_",
        env_nested_delimiter="__",
        extra="ignore",
    )
    
    makemkv: MakeMKVConfig = Field(default_factory=MakeMKVConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    devices: DeviceConfig = Field(default_factory=DeviceConfig)
    detection: DetectionConfig = Field(default_factory=DetectionConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    service: ServiceConfig = Field(default_factory=ServiceConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    
    @classmethod
    def from_yaml(cls, path: Path) -> Config:
        """Load configuration from YAML file."""
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        
        return cls(**data)
    
    def to_yaml(self, path: Path) -> None:
        """Save configuration to YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = self.model_dump()
        # Convert Path objects to strings
        def convert_paths(obj: Any) -> Any:
            if isinstance(obj, Path):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: convert_paths(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_paths(item) for item in obj]
            return obj
        
        data = convert_paths(data)
        
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    @classmethod
    def get_default_config(cls) -> Config:
        """Get default configuration."""
        return cls()


def find_config_file() -> Path | None:
    """Find configuration file in standard locations."""
    search_paths = [
        Path.home() / ".config" / "makemkv-auto" / "config.yaml",
        Path("/etc/makemkv-auto/config.yaml"),
        Path("/usr/local/etc/makemkv-auto/config.yaml"),
    ]
    
    for path in search_paths:
        if path.exists():
            return path
    
    return None


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from file or return defaults."""
    if config_path:
        return Config.from_yaml(config_path)
    
    found_path = find_config_file()
    if found_path:
        return Config.from_yaml(found_path)
    
    return Config.get_default_config()
