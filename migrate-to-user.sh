#!/bin/bash
# migrate-to-user.sh - Migrate makemkv-auto from system to user-level installation

set -e

echo "============================================"
echo "MakeMKV Auto - Migrate to User Installation"
echo "============================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root (we DON'T want this)
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}ERROR: Do not run this script as root/sudo!${NC}"
    echo "This script sets up user-level services."
    exit 1
fi

echo "This will:"
echo "  1. Stop and remove system-level services"
echo "  2. Uninstall the system-level package"
echo "  3. Install makemkv-auto at user level"
echo "  4. Set up user-level systemd services"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Step 1: Stopping system-level services..."
echo "-------------------------------------------"
sudo systemctl stop makemkv-auto-monitor makemkv-auto-web 2>/dev/null || true
sudo systemctl stop makemkv-auto-key.timer 2>/dev/null || true
echo -e "${GREEN}✓ Services stopped${NC}"

echo ""
echo "Step 2: Disabling system-level services..."
echo "--------------------------------------------"
sudo systemctl disable makemkv-auto-monitor makemkv-auto-web 2>/dev/null || true
sudo systemctl disable makemkv-auto-key.timer 2>/dev/null || true
echo -e "${GREEN}✓ Services disabled${NC}"

echo ""
echo "Step 3: Removing system-level service files..."
echo "------------------------------------------------"
sudo rm -f /etc/systemd/system/makemkv-auto-*.service
sudo systemctl daemon-reload
echo -e "${GREEN}✓ Service files removed${NC}"

echo ""
echo "Step 4: Uninstalling system-level package..."
echo "----------------------------------------------"
sudo python3.11 -m pip uninstall makemkv-auto -y 2>/dev/null || echo "Package not installed system-wide"
echo -e "${GREEN}✓ System package removed${NC}"

echo ""
echo "Step 5: Installing at user level..."
echo "-------------------------------------"
python3.11 -m pip install --user --force-reinstall /home/joseluis/Dev/ripping
echo -e "${GREEN}✓ Installed to user directory${NC}"

echo ""
echo "Step 6: Setting up user-level systemd services..."
echo "---------------------------------------------------"

# Create user systemd directory if needed
mkdir -p ~/.config/systemd/user

# Install services
makemkv-auto service install --user
echo -e "${GREEN}✓ Services installed${NC}"

echo ""
echo "Step 7: Enabling and starting services..."
echo "-------------------------------------------"
makemkv-auto service enable --user
makemkv-auto service start --user
echo -e "${GREEN}✓ Services enabled and started${NC}"

echo ""
echo "Step 8: Testing installation..."
echo "---------------------------------"
echo "Checking if makemkv-auto is available..."
which makemkv-auto && makemkv-auto --version
echo ""
echo "Checking service status..."
systemctl --user status makemkv-auto-monitor --no-pager || true

echo ""
echo "============================================"
echo -e "${GREEN}Migration complete!${NC}"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Check web UI: http://localhost:8766"
echo "  2. Test disc detection: makemkv-auto doctor"
echo "  3. View logs: makemkv-auto logs --user"
echo ""
echo "To manage services:"
echo "  makemkv-auto service start --user    # Start"
echo "  makemkv-auto service stop --user     # Stop"
echo "  makemkv-auto service status --user   # Status"
echo ""
echo "Note: Services run as your user ($(whoami))"
echo "      Config location: ~/.config/makemkv-auto/"
echo "      Log location: ~/.local/share/makemkv-auto/logs/"
