#!/bin/bash
# Quick fix script for systemd service user issue

set -e

echo "Fixing lora-osmnotes.service user configuration..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

# Detect user (pi, ubuntu, or current user)
if id "pi" &>/dev/null; then
    SERVICE_USER="pi"
elif id "ubuntu" &>/dev/null; then
    SERVICE_USER="ubuntu"
else
    SERVICE_USER="${SUDO_USER:-$USER}"
fi

echo "Detected service user: $SERVICE_USER"
echo "Verifying user exists..."
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "ERROR: User $SERVICE_USER does not exist!"
    echo "Please create the user or specify a different user."
    exit 1
fi

SERVICE_FILE="/etc/systemd/system/lora-osmnotes.service"

if [ ! -f "$SERVICE_FILE" ]; then
    echo "ERROR: Service file not found at $SERVICE_FILE"
    echo "Please install the service first using scripts/install_pi.sh"
    exit 1
fi

# Backup original
cp "$SERVICE_FILE" "${SERVICE_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
echo "Backup created: ${SERVICE_FILE}.backup.*"

# Update User line
sed -i "s/^User=.*/User=$SERVICE_USER/" "$SERVICE_FILE"

# Verify change
if grep -q "^User=$SERVICE_USER" "$SERVICE_FILE"; then
    echo "✓ Service file updated successfully"
else
    echo "ERROR: Failed to update service file"
    exit 1
fi

# Reload systemd
systemctl daemon-reload
echo "✓ Systemd daemon reloaded"

# Add user to dialout group if not already
if ! groups "$SERVICE_USER" | grep -q dialout; then
    usermod -a -G dialout "$SERVICE_USER"
    echo "✓ Added $SERVICE_USER to dialout group"
    echo "  Note: User may need to log out and back in for group changes to take effect"
else
    echo "✓ User $SERVICE_USER already in dialout group"
fi

echo ""
echo "Fix complete!"
echo ""
echo "You can now try to start the service:"
echo "  sudo systemctl start lora-osmnotes"
echo "  sudo systemctl status lora-osmnotes"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u lora-osmnotes -f"
