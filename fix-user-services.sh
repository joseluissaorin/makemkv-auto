#!/bin/bash
# fix-user-services.sh - Fix user-level systemd services

set -e

echo "Fixing user-level systemd services..."
echo ""

# Stop existing services
systemctl --user stop makemkv-auto-monitor makemkv-auto-web 2>/dev/null || true

# Remove old service files
rm -f ~/.config/systemd/user/makemkv-auto-*.service

# Reinstall package
python3.11 -m pip install --user --force-reinstall /home/joseluis/Dev/ripping 2>&1 | tail -3

# Reinstall services
makemkv-auto service install --user

# Reload and start
systemctl --user daemon-reload
systemctl --user start makemkv-auto-monitor

echo ""
echo "Checking status..."
sleep 2
systemctl --user status makemkv-auto-monitor --no-pager || true

echo ""
echo "To check logs: journalctl --user -u makemkv-auto-monitor -f"
