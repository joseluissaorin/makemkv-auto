# MakeMKV Auto

Automated MakeMKV disc ripper with intelligent TV/Movie detection and systemd integration.

## Features

- **Automatic Disc Detection**: Monitors optical drive and automatically rips discs
- **Smart Content Detection**: Automatically identifies TV shows vs movies based on duration and naming
- **Web UI Dashboard**: Monitor progress, view logs, and control the service from any device
- **Systemd Integration**: Full service management with auto-start on boot
- **Beta Key Management**: Automatic fetching and updating of MakeMKV beta keys
- **Desktop Notifications**: Get notified when rips complete
- **Comprehensive Logging**: File, journald, and structured logging options
- **Flexible Configuration**: YAML-based configuration with CLI overrides
- **Multi-drive Support**: Architecture supports multiple optical drives

## Requirements

- Python 3.11+
- Linux with systemd (recommended)
- Optical drive (DVD/Blu-ray)
- Root privileges (for service management and device access)

## Installation

### Quick Install

```bash
# Clone the repository
git clone https://github.com/yourusername/makemkv-auto.git
cd makemkv-auto

# Run the installation script
sudo bash scripts/install.sh
```

### Manual Install

```bash
# Install Python dependencies
pip install .

# Create directories
sudo mkdir -p /etc/makemkv-auto /var/log/makemkv-auto

# Copy default configuration
sudo cp config/config.yaml /etc/makemkv-auto/

# Install systemd services
sudo makemkv-auto service install
```

## Quick Start

```bash
# Check installation health
makemkv-auto doctor

# Install MakeMKV (if not already installed)
sudo makemkv-auto install

# Or install without beta key (MakeMKV will show dialog on first use)
sudo makemkv-auto install --skip-key-check

# Configure paths
makemkv-auto config set paths.base /path/to/your/media

# Update beta key
makemkv-auto key update

# Rip a disc manually
makemkv-auto rip

# Enable automatic ripping (one command!)
sudo makemkv-auto enable

# Or the manual way:
# sudo makemkv-auto service enable
# sudo makemkv-auto service start

# Disable auto-rip
sudo makemkv-auto disable
```

## Configuration

Configuration is stored in YAML format:

- **User config**: `~/.config/makemkv-auto/config.yaml`
- **System config**: `/etc/makemkv-auto/config.yaml`

### Example Configuration

```yaml
makemkv:
  version: "1.18.3"

paths:
  base: /media/storage
  movies: /media/storage/Movies
  tv_shows: /media/storage/TV

devices:
  primary: /dev/sr0

detection:
  auto_eject: true
  overwrite_existing: false

logging:
  level: INFO
  max_size: 100MB
```

## CLI Commands

### Core Commands

```bash
# Disc operations
makemkv-auto rip                    # Rip current disc
makemkv-auto rip --movie            # Force movie mode
makemkv-auto rip --tv-show          # Force TV show mode
makemkv-auto info                   # Show disc information
makemkv-auto eject                  # Eject disc

# Installation
makemkv-auto install                # Install MakeMKV
makemkv-auto doctor                 # Check installation health

# Configuration
makemkv-auto config init            # Create default config
makemkv-auto config show            # Display current config
makemkv-auto config edit            # Edit in $EDITOR
makemkv-auto config set key value   # Set a value

# Service Management (Shortcuts)
makemkv-auto enable                 # Enable and start auto-rip service (one command!)
makemkv-auto disable                # Disable and stop auto-rip service

# Web UI
makemkv-auto web status             # Check web UI status
makemkv-auto web url                # Show web UI URL
makemkv-auto web logs               # View web UI logs

# Service Management (Full)
makemkv-auto service install        # Install systemd services
makemkv-auto service enable         # Enable auto-start
makemkv-auto service start          # Start service
makemkv-auto service status         # Check status
makemkv-auto service logs           # View logs

# Beta Key
makemkv-auto key update             # Fetch latest beta key
makemkv-auto key show               # Display current key

# Logs
makemkv-auto logs                   # View application logs
makemkv-auto logs --follow          # Follow logs
```

## Service Management

The systemd service monitors your optical drive and automatically rips discs when inserted.

```bash
# Install services
sudo makemkv-auto service install

# Enable auto-start on boot
sudo makemkv-auto service enable

# Start the service
sudo makemkv-auto service start

# Check status
sudo makemkv-auto service status

# View service logs
sudo makemkv-auto service logs

# Stop service
sudo makemkv-auto service stop
```

## Web UI

MakeMKV Auto includes a built-in web UI for monitoring and controlling the service from any device on your network.

### Features

- **Real-time Dashboard**: View current ripping status with progress bars
- **Activity Logs**: Browse and filter application logs
- **System Information**: Check disk usage, service status, and configuration
- **Remote Control**: Eject discs and trigger actions from your browser
- **Browser Notifications**: Get notified when rips complete
- **Dark/Light Mode**: Automatically adapts to your system preference
- **Mobile Responsive**: Works on phones, tablets, and desktops

### Accessing the Web UI

Once the service is enabled, the web UI is available at:

```
http://your-server-ip:8766
```

The web UI automatically starts with the monitor service. To access it:

```bash
# Start the monitor service (web UI starts automatically)
sudo makemkv-auto enable

# Get the URL
makemkv-auto web url
```

### Web UI Commands

```bash
# Check if web UI is running
makemkv-auto web status

# Get the web UI URL
makemkv-auto web url

# View web UI logs
makemkv-auto web logs
makemkv-auto web logs --follow

# Manually control the web UI service
sudo makemkv-auto web start
sudo makemkv-auto web stop
sudo makemkv-auto web restart
```

### Configuration

Web UI settings can be configured in `config.yaml`:

```yaml
web:
  enabled: true              # Enable/disable web UI
  host: "0.0.0.0"           # Bind address (0.0.0.0 = all interfaces)
  port: 8766                # Port number
  auto_refresh: 5           # Dashboard refresh interval (seconds)
  log_lines: 100            # Default number of log lines to show
  auth:
    enabled: false          # Enable HTTP basic auth
    username: "admin"
    password: "changeme"    # Change this!
```

### Pages

- **Dashboard** (`/`): Current status, progress bars, last rip info, quick actions
- **Logs** (`/logs`): Filterable log viewer with download option
- **System** (`/system`): Disk usage, service status, configuration summary

### Security Notes

- By default, the web UI is accessible to anyone on your network
- No authentication is enabled by default (safe for home networks)
- To enable authentication, set `web.auth.enabled: true` in config
- Consider using a reverse proxy (nginx/traefik) with HTTPS for external access

## Development

```bash
# Install in development mode
make install-dev

# Run tests
make test

# Run linting
make lint

# Format code
make format
```

## Project Structure

```
makemkv_auto/
├── src/makemkv_auto/       # Main Python package
│   ├── cli.py              # CLI entry point
│   ├── config.py           # Configuration management
│   ├── ripper.py           # Disc ripping logic
│   ├── monitor.py          # Disc monitoring daemon
│   ├── installer.py        # MakeMKV installation
│   ├── beta_key.py         # Beta key management
│   ├── web/                # Web UI module
│   │   ├── app.py          # FastAPI application
│   │   ├── state.py        # Shared state management
│   │   ├── templates/      # HTML templates
│   │   └── static/         # CSS and assets
│   └── systemd/            # Systemd integration
├── systemd/                # Service file templates
├── config/                 # Default configurations
├── scripts/                # Installation scripts
└── tests/                  # Test suite
```

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Troubleshooting

### No disc detected

- Check device path: `makemkv-auto config show`
- Verify permissions: `ls -la /dev/sr*`
- Check drive: `makemkv-auto doctor`

### Rip fails

- Check MakeMKV installation: `makemkv-auto doctor`
- Verify beta key: `makemkv-auto key status`
- Check logs: `makemkv-auto logs`

### Service won't start

- Check systemd: `systemctl status makemkv-auto-monitor`
- Verify configuration: `makemkv-auto config validate`
- Check permissions: Ensure running as root
