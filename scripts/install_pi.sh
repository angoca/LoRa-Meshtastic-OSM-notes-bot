#!/bin/bash
# Installation script for Raspberry Pi OS

set -e

echo "Installing Meshtastic → OSM Notes Gateway..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Install system dependencies
echo "Installing system dependencies..."
apt-get update
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    gcc \
    git \
    sqlite3

# Detect user (pi, ubuntu, or current user)
if id "pi" &>/dev/null; then
    SERVICE_USER="pi"
elif id "ubuntu" &>/dev/null; then
    SERVICE_USER="ubuntu"
else
    SERVICE_USER="${SUDO_USER:-$USER}"
fi

echo "Detected service user: $SERVICE_USER"

# Create data directory
DATA_DIR="/var/lib/lora-osmnotes"
echo "Creating data directory: $DATA_DIR"
mkdir -p "$DATA_DIR"
chown "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR" 2>/dev/null || chown $SUDO_USER:$SUDO_USER "$DATA_DIR" 2>/dev/null || true

# Create virtual environment
VENV_DIR="/opt/lora-osmnotes"
echo "Creating virtual environment: $VENV_DIR"
mkdir -p "$VENV_DIR"
python3 -m venv "$VENV_DIR"

# Install Python dependencies
echo "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

# Install package in development mode
echo "Installing gateway package..."
cd "$PROJECT_DIR"
"$VENV_DIR/bin/pip" install -e .

# Copy environment file
if [ ! -f "$DATA_DIR/.env" ]; then
    echo "Creating .env file..."
    cp "$PROJECT_DIR/.env.example" "$DATA_DIR/.env"
    chmod 600 "$DATA_DIR/.env"
fi

# Install systemd service
echo "Installing systemd service..."
SERVICE_FILE="/etc/systemd/system/lora-osmnotes.service"
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Meshtastic → OSM Notes Gateway
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=dialout
WorkingDirectory=$DATA_DIR
Environment="PATH=$VENV_DIR/bin"
Environment="DATA_DIR=$DATA_DIR"
ExecStart=$VENV_DIR/bin/python -m gateway.main
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=lora-osmnotes

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Add user to dialout group for serial access
echo "Adding user $SERVICE_USER to dialout group..."
usermod -a -G dialout "$SERVICE_USER" 2>/dev/null || echo "Warning: Could not add user to dialout group"

# Reload systemd
systemctl daemon-reload

# Enable service (but don't start yet)
systemctl enable lora-osmnotes.service

echo ""
echo "Installation complete!"
echo ""
echo "Service user: $SERVICE_USER"
echo ""
echo "Next steps:"
echo "1. Edit $DATA_DIR/.env and set SERIAL_PORT (default: /dev/ttyACM0)"
echo "2. Connect your Meshtastic device"
echo "3. Check device: ls -l /dev/ttyACM*"
echo "4. Start service: sudo systemctl start lora-osmnotes"
echo "5. Check logs: sudo journalctl -u lora-osmnotes -f"
echo ""
echo "If you see 'Failed to determine user credentials' error:"
echo "  The service user was set to: $SERVICE_USER"
echo "  Verify this user exists: id $SERVICE_USER"
echo "  Or edit /etc/systemd/system/lora-osmnotes.service and change User="
echo ""
echo "To test in dry-run mode:"
echo "  Edit $DATA_DIR/.env and set DRY_RUN=true"
