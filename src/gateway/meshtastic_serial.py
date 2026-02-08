"""Meshtastic serial communication using meshtastic-python library."""

import logging
import time
import threading
from typing import Optional, Callable, Dict, Any

try:
    import meshtastic.serial_interface
    MESHTASTIC_AVAILABLE = True
except ImportError:
    MESHTASTIC_AVAILABLE = False

from .config import SERIAL_PORT

logger = logging.getLogger(__name__)


class MeshtasticSerial:
    """
    Meshtastic serial connection using meshtastic-python library.
    
    Manages USB serial communication with Meshtastic devices using the
    official meshtastic-python library. Handles connection, reconnection,
    message parsing (protobuf), and sending DMs/broadcasts.
    
    Attributes:
        port: Serial port path (e.g., "/dev/ttyUSB0")
        interface: meshtastic SerialInterface object
        running: Flag indicating if reader thread is running
        message_callback: Callback function for incoming messages
        position_cache: Cache for node positions (node_id -> (lat, lon, timestamp))
        
    Note:
        Uses meshtastic-python library to parse protobuf packets and handle
        real Meshtastic protocol communication.
    """

    def __init__(
        self,
        port: str = SERIAL_PORT,
        baudrate: int = 9600,  # Not used with meshtastic library, kept for compatibility
        timeout: float = 1.0,  # Not used with meshtastic library, kept for compatibility
    ):
        if not MESHTASTIC_AVAILABLE:
            raise ImportError(
                "meshtastic library not available. Install with: pip install meshtastic"
            )

        self.port = port
        self.interface: Optional[meshtastic.serial_interface.SerialInterface] = None
        self.running = False
        self.reconnect_delay = 5.0
        self.message_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self.position_cache: Dict[str, Dict[str, Any]] = {}  # node_id -> {lat, lon, timestamp}
        self._lock = threading.Lock()

    def set_message_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback for incoming messages."""
        self.message_callback = callback

    def connect(self) -> bool:
        """Connect to Meshtastic device."""
        try:
            if self.interface:
                # Check if still connected
                try:
                    # Try to get node info to verify connection
                    _ = self.interface.getMyNodeInfo()
                    return True
                except Exception:
                    # Connection lost, need to reconnect
                    self.interface = None

            logger.info(f"Connecting to Meshtastic device at {self.port}...")
            self.interface = meshtastic.serial_interface.SerialInterface(
                devPath=self.port,
                noProto=False,
                connectNow=True,
            )
            logger.info(f"Connected to Meshtastic device at {self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to {self.port}: {e}")
            self.interface = None
            return False

    def disconnect(self):
        """Disconnect from Meshtastic device."""
        self.running = False
        if self.interface:
            try:
                self.interface.close()
                logger.info("Disconnected from Meshtastic device")
            except Exception as e:
                logger.debug(f"Error closing interface: {e}")
            finally:
                self.interface = None

    def start(self):
        """Start message listener."""
        if self.running:
            return

        if not self.connect():
            logger.error("Failed to connect, cannot start")
            return

        self.running = True

        # Subscribe to receive messages
        self.interface.subscribe(self._on_receive)

        logger.info("Meshtastic serial reader started")

    def stop(self):
        """Stop message listener."""
        self.running = False
        self.disconnect()

    def _on_receive(self, packet, interface):
        """Handle received packet from Meshtastic."""
        if not self.running or not self.message_callback:
            return

        try:
            # Extract message data
            decoded = packet.get("decoded", {})
            portnum = decoded.get("portnum")

            # Handle text messages (portnum can be string "TEXT_MESSAGE_APP" or number)
            if portnum == "TEXT_MESSAGE_APP" or (isinstance(portnum, int) and portnum == 1):
                text = decoded.get("text", "")
                from_node = packet.get("from")
                
                if not from_node or not text:
                    return

                # Convert node number to string format (Meshtastic uses 8-char hex)
                if isinstance(from_node, int):
                    # Format as !12345678 (8 hex chars, lowercase)
                    node_id = f"!{from_node:08x}"
                else:
                    node_id = str(from_node)
                    # Ensure it starts with ! if it's a hex string
                    if not node_id.startswith("!") and len(node_id) > 0:
                        node_id = f"!{node_id}"

                # Get position from cache if available
                position = self.position_cache.get(node_id, {})
                lat = position.get("lat")
                lon = position.get("lon")

                logger.info(f"Received message from {node_id}: {text[:50]}...")

                # Call callback with message data
                self.message_callback({
                    "node_id": node_id,
                    "lat": lat,
                    "lon": lon,
                    "text": text,
                    "timestamp": time.time(),
                })

            # Handle position updates (portnum can be string "POSITION_APP" or number)
            elif portnum == "POSITION_APP" or (isinstance(portnum, int) and portnum == 3):
                from_node = packet.get("from")
                position_data = decoded.get("position", {})
                
                if from_node and position_data:
                    if isinstance(from_node, int):
                        node_id = f"!{from_node:08x}"
                    else:
                        node_id = str(from_node)
                        if not node_id.startswith("!") and len(node_id) > 0:
                            node_id = f"!{node_id}"
                    
                    # Extract position (Meshtastic uses integer coordinates)
                    lat_i = position_data.get("latitudeI")
                    lon_i = position_data.get("longitudeI")
                    
                    if lat_i is not None and lon_i is not None:
                        # Convert from integer (1e-7 degrees) to float
                        lat = lat_i / 1e7
                        lon = lon_i / 1e7
                        
                        # Update position cache
                        with self._lock:
                            self.position_cache[node_id] = {
                                "lat": lat,
                                "lon": lon,
                                "timestamp": time.time(),
                            }
                        
                        logger.debug(f"Updated position for {node_id}: {lat}, {lon}")

            # Handle telemetry (may contain position) (portnum can be string "TELEMETRY_APP" or number)
            elif portnum == "TELEMETRY_APP" or (isinstance(portnum, int) and portnum == 67):
                from_node = packet.get("from")
                telemetry = decoded.get("telemetry", {})
                
                if from_node and telemetry:
                    if isinstance(from_node, int):
                        node_id = f"!{from_node:08x}"
                    else:
                        node_id = str(from_node)
                        if not node_id.startswith("!") and len(node_id) > 0:
                            node_id = f"!{node_id}"
                    
                    # Check for position in device metrics
                    device_metrics = telemetry.get("device")
                    if device_metrics:
                        # Telemetry doesn't directly contain position, but we log it
                        logger.debug(f"Received telemetry from {node_id}")

        except Exception as e:
            logger.error(f"Error processing packet: {e}")

    def send_dm(self, node_id: str, message: str) -> bool:
        """Send direct message to a node."""
        if not self.interface:
            logger.warning("Interface not connected, cannot send DM")
            return False

        try:
            # Convert node_id format if needed
            # Meshtastic expects node number (int) or node ID string (like "!12345678")
            node_num = None
            
            if node_id.startswith("!"):
                # Extract node number from ID format "!12345678" or "!9e7878a4"
                try:
                    # Try parsing as hex (8 chars) or full hex (16 chars)
                    hex_part = node_id[1:]
                    if len(hex_part) == 8:
                        # Short format: convert to int
                        node_num = int(hex_part, 16)
                    elif len(hex_part) == 16:
                        # Long format: use the last 8 chars or convert full
                        node_num = int(hex_part[-8:], 16) if len(hex_part) >= 8 else int(hex_part, 16)
                    else:
                        node_num = int(hex_part, 16)
                except ValueError:
                    # Try to find node in nodes dict by ID string
                    nodes = self.interface.nodes
                    if node_id in nodes:
                        node_num = nodes[node_id].get("num")
                    else:
                        logger.error(f"Invalid node_id format: {node_id}")
                        return False
            else:
                # Try as integer directly
                try:
                    node_num = int(node_id)
                except ValueError:
                    # Try to find in nodes dict
                    nodes = self.interface.nodes
                    for nid, node_info in nodes.items():
                        if nid == node_id or str(node_info.get("num")) == node_id:
                            node_num = node_info.get("num")
                            break
                    if node_num is None:
                        logger.error(f"Invalid node_id format: {node_id}")
                        return False

            if node_num is None:
                logger.error(f"Could not determine node number for {node_id}")
                return False

            # Send message
            self.interface.sendText(message, destinationId=node_num, wantAck=False)
            logger.info(f"Sent DM to {node_id} (node_num={node_num}): {message[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to send DM to {node_id}: {e}")
            return False

    def send_broadcast(self, message: str) -> bool:
        """Send broadcast message."""
        if not self.interface:
            logger.warning("Interface not connected, cannot send broadcast")
            return False

        try:
            # Send broadcast (no destination = broadcast)
            self.interface.sendText(message, wantAck=False)
            logger.info(f"Sent broadcast: {message[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to send broadcast: {e}")
            return False
