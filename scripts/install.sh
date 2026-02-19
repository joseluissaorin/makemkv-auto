#!/bin/bash
#
# MakeMKV Auto Installation Script
# This script installs the makemkv-auto Python package and sets up systemd services
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
INSTALL_PREFIX="/usr/local"
CONFIG_DIR="/etc/makemkv-auto"
LOG_DIR="/var/log/makemkv-auto"
SERVICE_DIR="/etc/systemd/system"

# Functions
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        error "This script must be run as root (use sudo)"
    fi
}

check_python() {
    log "Checking Python version..."
    
    # Look for Python 3.11+ in order of preference
    PYTHON_CMD=""
    
    # Check for specific versions from newest to oldest
    for py in python3.13 python3.12 python3.11; do
        if command -v "$py" &> /dev/null; then
            PYTHON_CMD="$py"
            break
        fi
    done
    
    # Fallback to python3 if no specific version found
    if [ -z "$PYTHON_CMD" ]; then
        if command -v python3 &> /dev/null; then
            PYTHON_CMD="python3"
        else
            error "Python 3 is not installed"
        fi
    fi
    
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
    REQUIRED_VERSION="3.11"
    
    if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
        error "Python $PYTHON_VERSION is installed, but Python $REQUIRED_VERSION+ is required. Please install Python 3.11 or newer."
    fi
    
    log "Python $PYTHON_VERSION found ($PYTHON_CMD) ✓"
    export PYTHON_CMD
}

install_python_deps() {
    log "Installing Python dependencies..."
    
    # Ensure pip is installed for the selected Python
    if ! "$PYTHON_CMD" -m pip --version &> /dev/null; then
        log "Installing pip for $PYTHON_CMD..."
        apt-get update
        # Install pip for the specific Python version
        apt-get install -y "${PYTHON_CMD}-pip" python3-venv 2>/dev/null || apt-get install -y python3-pip python3-venv
    fi
    
    # Install the package
    log "Installing makemkv-auto package..."
    
    # Get the directory where this script is located
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && cd .. && pwd )"
    
    # Install in development mode or from the local directory
    if [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
        "$PYTHON_CMD" -m pip install --force-reinstall "$SCRIPT_DIR"
    else
        "$PYTHON_CMD" -m pip install --force-reinstall makemkv-auto
    fi
    
    log "Package installed ✓"
}

setup_directories() {
    log "Creating directories..."
    
    # Create config directory
    mkdir -p "$CONFIG_DIR"
    chmod 755 "$CONFIG_DIR"
    
    # Create log directory
    mkdir -p "$LOG_DIR"
    chmod 755 "$LOG_DIR"
    
    log "Directories created ✓"
}

setup_config() {
    log "Setting up configuration..."
    
    CONFIG_FILE="$CONFIG_DIR/config.yaml"
    
    if [ -f "$CONFIG_FILE" ]; then
        warning "Configuration file already exists at $CONFIG_FILE"
        info "Run 'makemkv-auto config edit' to modify it"
    else
        # Copy default config
        SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && cd .. && pwd )"
        if [ -f "$SCRIPT_DIR/config/config.yaml" ]; then
            cp "$SCRIPT_DIR/config/config.yaml" "$CONFIG_FILE"
        else
            # Create minimal config
            cat > "$CONFIG_FILE" << 'EOF'
makemkv:
  version: "1.18.3"
  install_path: /usr/local

paths:
  base: /media/joseluis/DATOS_HDD/datos_samba
  temp: /tmp/makemkv-auto
  logs: /var/log/makemkv-auto

devices:
  primary: /dev/sr0
  additional: []

detection:
  min_episode_duration: 18
  max_episode_duration: 70
  min_movie_duration: 75
  auto_eject: true
  overwrite_existing: false

output:
  naming_pattern: "{title}"
  create_nfo: false
  min_length: 600

logging:
  level: INFO
  max_size: 100MB
  retention_days: 30
  structured: false

service:
  check_interval: 5
  retry_count: 3
  retry_delay: 10
EOF
        fi
        
        log "Configuration file created at $CONFIG_FILE"
    fi
}

install_systemd_services() {
    log "Installing systemd services..."
    
    # Check if systemd is available
    if ! command -v systemctl &> /dev/null; then
        warning "systemctl not found, skipping service installation"
        return
    fi
    
    # Install services using the CLI
    makemkv-auto service install
    
    log "Services installed ✓"
    info "Enable auto-rip with: sudo makemkv-auto service enable"
    info "Start service with: sudo makemkv-auto service start"
}

set_permissions() {
    log "Setting permissions..."
    
    # Add current user to cdrom group if possible
    if [ -n "$SUDO_USER" ]; then
        usermod -a -G cdrom "$SUDO_USER" 2>/dev/null || true
        info "Added $SUDO_USER to cdrom group"
    fi
    
    # Ensure device is readable
    if [ -e "/dev/sr0" ]; then
        chmod 666 /dev/sr0 2>/dev/null || true
    fi
}

show_post_install() {
    echo ""
    echo "========================================"
    echo "Installation Complete!"
    echo "========================================"
    echo ""
    echo "Quick Start:"
    echo "  1. Check installation:  makemkv-auto doctor"
    echo "  2. View config:         makemkv-auto config show"
    echo "  3. Edit config:         makemkv-auto config edit"
    echo "  4. Install MakeMKV:     sudo makemkv-auto install"
    echo "  5. Rip a disc:          makemkv-auto rip"
    echo ""
    echo "Auto-Rip Service:"
    echo "  Enable:   sudo makemkv-auto service enable"
    echo "  Start:    sudo makemkv-auto service start"
    echo "  Status:   sudo makemkv-auto service status"
    echo ""
    echo "Logs:"
    echo "  App logs: makemkv-auto logs"
    echo "  Service:  makemkv-auto service logs"
    echo ""
    echo "Configuration: $CONFIG_DIR/config.yaml"
    echo "Log directory: $LOG_DIR"
    echo ""
}

main() {
    log "Starting MakeMKV Auto installation..."
    
    check_root
    check_python
    install_python_deps
    setup_directories
    setup_config
    install_systemd_services
    set_permissions
    
    log "Installation complete!"
    show_post_install
}

main "$@"
