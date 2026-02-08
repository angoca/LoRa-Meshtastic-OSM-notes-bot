#!/bin/bash
# Script to disable Bluetooth on Heltec V3 Meshtastic device
# Usage: sudo bash scripts/deshabilitar_bluetooth.sh [PORT]

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to detect serial port automatically
detect_serial_port() {
    # First, try to get from .env file
    if [ -f "/var/lib/lora-osmnotes/.env" ]; then
        ENV_PORT=$(grep "^SERIAL_PORT=" /var/lib/lora-osmnotes/.env 2>/dev/null | cut -d'=' -f2 | tr -d '"' | tr -d "'" | tr -d ' ')
        if [ -n "$ENV_PORT" ] && [ -e "$ENV_PORT" ]; then
            echo "$ENV_PORT"
            return
        fi
    fi
    
    # Try to find first available USB device (ttyUSB* first, then ttyACM*)
    for device in /dev/ttyUSB* /dev/ttyACM*; do
        if [ -e "$device" ]; then
            echo "$device"
            return
        fi
    done
    
    # Default fallback
    echo "/dev/ttyUSB0"
}

# Get serial port from argument or auto-detect
if [ -n "$1" ]; then
    SERIAL_PORT="$1"
else
    SERIAL_PORT=$(detect_serial_port)
fi

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
    exit 1
fi

echo "=========================================="
echo "Deshabilitar Bluetooth en Heltec V3"
echo "=========================================="
echo ""

# Check if device exists
if [ ! -e "$SERIAL_PORT" ]; then
    echo -e "${RED}Error: Device $SERIAL_PORT not found${NC}"
    echo ""
    echo "Available devices:"
    ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo "  No serial devices found"
    exit 1
fi

echo "Using device: $SERIAL_PORT"
echo ""

# Check if meshtastic CLI is available
MESHTASTIC_CMD=""
if [ -f "/opt/lora-osmnotes/bin/meshtastic" ]; then
    MESHTASTIC_CMD="/opt/lora-osmnotes/bin/meshtastic"
elif command -v meshtastic &> /dev/null; then
    MESHTASTIC_CMD="meshtastic"
else
    echo -e "${RED}Error: meshtastic CLI not found${NC}"
    exit 1
fi

# Stop the service if it's running
if systemctl is-active --quiet lora-osmnotes; then
    echo -e "${YELLOW}Stopping lora-osmnotes service...${NC}"
    systemctl stop lora-osmnotes
    SERVICE_WAS_RUNNING=true
else
    SERVICE_WAS_RUNNING=false
fi

sleep 2

# Disable Bluetooth
echo -e "${GREEN}Disabling Bluetooth on $SERIAL_PORT...${NC}"
if $MESHTASTIC_CMD --port "$SERIAL_PORT" --set bluetooth.enabled false; then
    echo -e "${GREEN}✓ Bluetooth disabled successfully${NC}"
else
    echo -e "${RED}✗ Failed to disable Bluetooth${NC}"
    if [ "$SERVICE_WAS_RUNNING" = true ]; then
        systemctl start lora-osmnotes
    fi
    exit 1
fi

sleep 5

# Restart service if it was running
if [ "$SERVICE_WAS_RUNNING" = true ]; then
    echo "Restarting lora-osmnotes service..."
    systemctl start lora-osmnotes
fi

echo ""
echo -e "${GREEN}Done!${NC}"
echo ""
