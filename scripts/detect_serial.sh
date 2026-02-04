#!/bin/bash
# Script to detect Meshtastic serial devices
# Usage: ./detect_serial.sh

set -e

echo "Detecting Meshtastic serial devices..."
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check for common serial devices
DEVICES_FOUND=0

echo "Checking /dev/ttyACM* devices:"
for device in /dev/ttyACM*; do
    if [ -e "$device" ]; then
        DEVICES_FOUND=$((DEVICES_FOUND + 1))
        echo -e "  ${GREEN}✓${NC} Found: $device"
        
        # Get device info
        if command -v udevadm &> /dev/null; then
            DEVICE_INFO=$(udevadm info --query=property --name="$device" 2>/dev/null | grep -E "ID_VENDOR|ID_MODEL|ID_SERIAL_SHORT" | head -3)
            if [ -n "$DEVICE_INFO" ]; then
                echo "    Info:"
                echo "$DEVICE_INFO" | sed 's/^/      /'
            fi
        fi
        
        # Check permissions
        PERMS=$(stat -c "%a %U:%G" "$device" 2>/dev/null || stat -f "%OLp %Su:%Sg" "$device" 2>/dev/null)
        echo "    Permissions: $PERMS"
        
        # Check if current user can access
        if [ -r "$device" ] && [ -w "$device" ]; then
            echo -e "    ${GREEN}✓${NC} Readable and writable by current user"
        else
            echo -e "    ${YELLOW}⚠${NC} Not accessible by current user"
            echo "      Add user to dialout group: sudo usermod -a -G dialout $USER"
            echo "      Then logout and login again"
        fi
        echo ""
    fi
done

if [ $DEVICES_FOUND -eq 0 ]; then
    echo -e "  ${YELLOW}No /dev/ttyACM* devices found${NC}"
fi

echo "Checking /dev/ttyUSB* devices:"
for device in /dev/ttyUSB*; do
    if [ -e "$device" ]; then
        DEVICES_FOUND=$((DEVICES_FOUND + 1))
        echo -e "  ${GREEN}✓${NC} Found: $device"
        
        # Get device info
        if command -v udevadm &> /dev/null; then
            DEVICE_INFO=$(udevadm info --query=property --name="$device" 2>/dev/null | grep -E "ID_VENDOR|ID_MODEL|ID_SERIAL_SHORT" | head -3)
            if [ -n "$DEVICE_INFO" ]; then
                echo "    Info:"
                echo "$DEVICE_INFO" | sed 's/^/      /'
            fi
        fi
        
        # Check permissions
        PERMS=$(stat -c "%a %U:%G" "$device" 2>/dev/null || stat -f "%OLp %Su:%Sg" "$device" 2>/dev/null)
        echo "    Permissions: $PERMS"
        
        # Check if current user can access
        if [ -r "$device" ] && [ -w "$device" ]; then
            echo -e "    ${GREEN}✓${NC} Readable and writable by current user"
        else
            echo -e "    ${YELLOW}⚠${NC} Not accessible by current user"
            echo "      Add user to dialout group: sudo usermod -a -G dialout $USER"
            echo "      Then logout and login again"
        fi
        echo ""
    fi
done

if [ $DEVICES_FOUND -eq 0 ]; then
    echo -e "${YELLOW}No serial devices found.${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "1. Make sure your Meshtastic device is connected via USB"
    echo "2. Check USB connection: lsusb | grep -i meshtastic"
    echo "3. Check if device is recognized: dmesg | tail -20"
    echo "4. Try unplugging and replugging the device"
    exit 1
fi

echo "USB devices (checking for Meshtastic):"
if command -v lsusb &> /dev/null; then
    USB_MESHTASTIC=$(lsusb | grep -i meshtastic || true)
    if [ -n "$USB_MESHTASTIC" ]; then
        echo -e "  ${GREEN}✓${NC} Found Meshtastic device:"
        echo "$USB_MESHTASTIC" | sed 's/^/    /'
    else
        echo -e "  ${YELLOW}⚠${NC} No Meshtastic device found in USB list"
        echo "    All USB devices:"
        lsusb | sed 's/^/      /'
    fi
else
    echo "  lsusb not available, skipping USB check"
fi

echo ""
echo "Current user groups:"
GROUPS=$(groups)
echo "  $GROUPS"
if echo "$GROUPS" | grep -q dialout; then
    echo -e "  ${GREEN}✓${NC} User is in dialout group"
else
    echo -e "  ${YELLOW}⚠${NC} User is NOT in dialout group"
    echo "  Add with: sudo usermod -a -G dialout $USER"
    echo "  Then logout and login again"
fi

echo ""
echo "Recommendation:"
if [ $DEVICES_FOUND -gt 0 ]; then
    # Find first available device
    FIRST_DEVICE=""
    for device in /dev/ttyACM* /dev/ttyUSB*; do
        if [ -e "$device" ]; then
            FIRST_DEVICE="$device"
            break
        fi
    done
    
    if [ -n "$FIRST_DEVICE" ]; then
        echo "  Set SERIAL_PORT=$FIRST_DEVICE in /var/lib/lora-osmnotes/.env"
        echo ""
        echo "  Example:"
        echo "    sudo nano /var/lib/lora-osmnotes/.env"
        echo "    # Change SERIAL_PORT to:"
        echo "    SERIAL_PORT=$FIRST_DEVICE"
    fi
else
    echo "  Connect your Meshtastic device and run this script again"
fi
