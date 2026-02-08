#!/bin/bash
# Script to enable Bluetooth on Heltec V3 Meshtastic device
# Usage: sudo bash scripts/habilitar_bluetooth.sh [PORT]
# Example: sudo bash scripts/habilitar_bluetooth.sh /dev/ttyACM0

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get serial port from argument or use default
SERIAL_PORT="${1:-/dev/ttyACM0}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
    exit 1
fi

echo "=========================================="
echo "Habilitar Bluetooth en Heltec V3"
echo "=========================================="
echo ""

# Check if device exists
if [ ! -e "$SERIAL_PORT" ]; then
    echo -e "${RED}Error: Device $SERIAL_PORT not found${NC}"
    echo ""
    echo "Available devices:"
    ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || echo "  No serial devices found"
    exit 1
fi

echo "Device: $SERIAL_PORT"
echo ""

# Check if meshtastic CLI is available
MESHTASTIC_CMD=""
if [ -f "/opt/lora-osmnotes/bin/meshtastic" ]; then
    MESHTASTIC_CMD="/opt/lora-osmnotes/bin/meshtastic"
    echo "Using: $MESHTASTIC_CMD"
elif command -v meshtastic &> /dev/null; then
    MESHTASTIC_CMD="meshtastic"
    echo "Using: $MESHTASTIC_CMD"
else
    echo -e "${RED}Error: meshtastic CLI not found${NC}"
    echo ""
    echo "Install with:"
    echo "  pip3 install meshtastic"
    echo "  OR use the one from /opt/lora-osmnotes/bin/meshtastic"
    exit 1
fi

# Stop the service if it's running
echo ""
echo "Checking service status..."
if systemctl is-active --quiet lora-osmnotes; then
    echo -e "${YELLOW}Stopping lora-osmnotes service...${NC}"
    systemctl stop lora-osmnotes
    SERVICE_WAS_RUNNING=true
else
    SERVICE_WAS_RUNNING=false
    echo "Service is not running"
fi

# Wait a moment for the service to release the port
sleep 2

# Enable Bluetooth
echo ""
echo -e "${GREEN}Enabling Bluetooth on $SERIAL_PORT...${NC}"
echo ""

# Try to enable Bluetooth
if $MESHTASTIC_CMD --port "$SERIAL_PORT" --set bluetooth.enabled true; then
    echo ""
    echo -e "${GREEN}✓ Bluetooth enabled successfully${NC}"
else
    echo ""
    echo -e "${RED}✗ Failed to enable Bluetooth${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "1. Check if device is connected: lsusb | grep -i meshtastic"
    echo "2. Check permissions: ls -l $SERIAL_PORT"
    echo "3. Try manually: $MESHTASTIC_CMD --port $SERIAL_PORT --set bluetooth.enabled true"
    
    # Restart service if it was running
    if [ "$SERVICE_WAS_RUNNING" = true ]; then
        echo ""
        echo "Restarting service..."
        systemctl start lora-osmnotes
    fi
    
    exit 1
fi

# Wait a moment for device to reboot
echo ""
echo "Waiting for device to reboot (5 seconds)..."
sleep 5

# Verify Bluetooth is enabled
echo ""
echo "Verifying Bluetooth status..."
BLUETOOTH_STATUS=$($MESHTASTIC_CMD --port "$SERIAL_PORT" --info 2>/dev/null | grep -i "bluetooth" || echo "")
if [ -n "$BLUETOOTH_STATUS" ]; then
    echo "Bluetooth info:"
    echo "$BLUETOOTH_STATUS" | sed 's/^/  /'
else
    echo -e "${YELLOW}Could not verify Bluetooth status (this is OK)${NC}"
fi

# Restart service if it was running
if [ "$SERVICE_WAS_RUNNING" = true ]; then
    echo ""
    echo -e "${GREEN}Restarting lora-osmnotes service...${NC}"
    systemctl start lora-osmnotes
    
    # Check service status
    sleep 2
    if systemctl is-active --quiet lora-osmnotes; then
        echo -e "${GREEN}✓ Service restarted successfully${NC}"
    else
        echo -e "${YELLOW}⚠ Service may not have started. Check with: sudo systemctl status lora-osmnotes${NC}"
    fi
fi

echo ""
echo "=========================================="
echo -e "${GREEN}Done!${NC}"
echo "=========================================="
echo ""
echo "You can now connect to the Heltec V3 via Bluetooth from your phone."
echo ""
echo "To verify Bluetooth is working:"
echo "  1. Open Meshtastic app on your phone"
echo "  2. Look for a device named 'Meshtastic' or similar"
echo "  3. Connect to it"
echo ""
echo "To disable Bluetooth again:"
echo "  sudo $MESHTASTIC_CMD --port $SERIAL_PORT --set bluetooth.enabled false"
echo ""
