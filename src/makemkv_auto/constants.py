"""Constants and default values."""

from pathlib import Path

# Application info
APP_NAME = "makemkv-auto"
APP_VERSION = "1.0.0"

# Default paths
DEFAULT_CONFIG_DIR = Path("/etc") / APP_NAME
DEFAULT_USER_CONFIG_DIR = Path.home() / ".config" / APP_NAME
DEFAULT_LOG_DIR = Path("/var/log") / APP_NAME
DEFAULT_TEMP_DIR = Path("/tmp") / APP_NAME

# MakeMKV
MAKEMKV_DEFAULT_VERSION = "1.18.3"
MAKEMKV_DOWNLOAD_URL = "https://www.makemkv.com/download"
MAKEMKV_BETA_KEY_URL = "https://www.makemkv.com/forum2/viewtopic.php?f=5&t=1053"

# Device defaults
DEFAULT_DEVICE = "/dev/sr0"

# Detection defaults (in minutes)
DEFAULT_MIN_EPISODE_DURATION = 18
DEFAULT_MAX_EPISODE_DURATION = 70
DEFAULT_MIN_MOVIE_DURATION = 75

# Service defaults
DEFAULT_CHECK_INTERVAL = 5  # seconds
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY = 10  # seconds

# Output defaults
DEFAULT_NAMING_PATTERN = "{title}"
DEFAULT_MIN_LENGTH = 600  # seconds (10 minutes)

# Logging defaults
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_MAX_SIZE = "100MB"
DEFAULT_LOG_RETENTION_DAYS = 30

# Systemd
SYSTEMD_SERVICE_NAME = "makemkv-auto-monitor.service"
SYSTEMD_TIMER_NAME = "makemkv-auto-key.timer"

# File permissions
DEFAULT_DIR_MODE = 0o755
DEFAULT_FILE_MODE = 0o644
