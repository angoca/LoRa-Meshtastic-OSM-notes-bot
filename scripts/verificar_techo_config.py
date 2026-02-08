#!/usr/bin/env python3
"""Script to check T-Echo configuration and position status."""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import meshtastic.serial_interface
    from pubsub import pub
except ImportError:
    print("ERROR: meshtastic library not available. Install with: pip install meshtastic")
    sys.exit(1)

import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

def find_techo_nodes(interface):
    """Find all T-Echo nodes in the mesh."""
    techo_nodes = []
    
    print("\n=== Searching for T-Echo devices ===")
    nodes = interface.nodes
    print(f"Total nodes in mesh: {len(nodes)}")
    
    for node_num, node_info in nodes.items():
        user_info = node_info.get("user", {})
        hw_model = user_info.get("hwModel", "")
        node_id = user_info.get("id", "")
        long_name = user_info.get("longName", "")
        
        is_techo = (
            "T_ECHO" in str(hw_model) or
            "techo" in str(hw_model).lower() or
            "t-echo" in str(hw_model).lower() or
            "lilygo" in str(hw_model).lower()
        )
        
        if is_techo:
            print(f"\n✓ Found T-Echo: {node_id} ({long_name})")
            techo_nodes.append((node_num, node_id, node_info))
        else:
            print(f"  Node {node_id}: {hw_model}")
    
    return techo_nodes

def check_node_position(node_num, node_id, node_info):
    """Check position information for a node."""
    print(f"\n=== Position check for {node_id} ===")
    
    # Check position in nodeinfo
    position_info = node_info.get("position")
    if position_info:
        print(f"✓ Position found in nodeinfo:")
        print(f"  Keys: {list(position_info.keys())}")
        
        if "latitudeI" in position_info and "longitudeI" in position_info:
            lat_i = position_info.get("latitudeI")
            lon_i = position_info.get("longitudeI")
            if lat_i is not None and lon_i is not None:
                lat = lat_i / 1e7
                lon = lon_i / 1e7
                print(f"  Coordinates: ({lat}, {lon})")
                
                # Check if position is valid (not 0,0)
                if lat == 0.0 and lon == 0.0:
                    print(f"  ⚠️  WARNING: Position is (0,0) - invalid!")
                else:
                    print(f"  ✓ Position appears valid")
            else:
                print(f"  ⚠️  Position integers are None")
        else:
            print(f"  ⚠️  Position doesn't have latitudeI/longitudeI")
            
        # Check position time
        pos_time = position_info.get("time")
        if pos_time:
            import time
            age = time.time() - pos_time
            print(f"  Position age: {age:.0f} seconds ({age/60:.1f} minutes)")
        
        # Check location source
        location_source = position_info.get("locationSource", "")
        print(f"  Location source: {location_source}")
    else:
        print(f"✗ NO position in nodeinfo")
    
    # Check device metrics
    device_metrics = node_info.get("deviceMetrics")
    if device_metrics:
        uptime = device_metrics.get("uptimeSeconds")
        battery = device_metrics.get("batteryLevel")
        print(f"\nDevice metrics:")
        print(f"  Uptime: {uptime} seconds ({uptime/60:.1f} minutes)")
        print(f"  Battery: {battery}%")
    else:
        print(f"\n⚠️  No device metrics available")

def check_local_config(interface):
    """Check local node configuration for position broadcast settings."""
    print(f"\n=== Local node configuration ===")
    try:
        local_node = interface.getNode("^local")
        if hasattr(local_node, "localConfig") and hasattr(local_node.localConfig, "position"):
            pos_config = local_node.localConfig.position
            print(f"Position broadcast interval: {getattr(pos_config, 'position_broadcast_secs', 'NOT SET')} seconds")
        else:
            print("⚠️  Could not access position config")
    except Exception as e:
        print(f"⚠️  Error checking local config: {e}")

def main():
    """Main function."""
    serial_port = os.getenv("SERIAL_PORT", "/dev/ttyACM0")
    
    print(f"Connecting to Meshtastic device at {serial_port}...")
    try:
        interface = meshtastic.serial_interface.SerialInterface(
            devPath=serial_port,
            noProto=False,
            connectNow=True,
        )
        print("✓ Connected")
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        return 1
    
    try:
        # Wait a bit for node info to populate
        import time
        print("\nWaiting 3 seconds for node info to populate...")
        time.sleep(3)
        
        # Check local config
        check_local_config(interface)
        
        # Find T-Echo nodes
        techo_nodes = find_techo_nodes(interface)
        
        if not techo_nodes:
            print("\n⚠️  No T-Echo devices found in mesh")
            print("\nAll nodes:")
            for node_num, node_info in interface.nodes.items():
                user_info = node_info.get("user", {})
                print(f"  - {user_info.get('id', 'unknown')}: {user_info.get('hwModel', 'unknown')}")
        else:
            # Check each T-Echo
            for node_num, node_id, node_info in techo_nodes:
                check_node_position(node_num, node_id, node_info)
        
        print("\n=== Summary ===")
        print("To enable position broadcasting on T-Echo:")
        print("1. Connect to T-Echo via Meshtastic app or CLI")
        print("2. Go to Position settings")
        print("3. Enable 'Position Broadcast'")
        print("4. Set broadcast interval to 60 seconds (minimum)")
        print("5. Ensure GPS has signal (device should be outdoors)")
        
    finally:
        interface.close()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
