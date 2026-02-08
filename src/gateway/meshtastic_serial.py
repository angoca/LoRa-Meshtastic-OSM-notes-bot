"""Meshtastic serial communication using meshtastic-python library."""

import logging
import time
import threading
from typing import Optional, Callable, Dict, Any

try:
    import meshtastic.serial_interface
    from pubsub import pub
    MESHTASTIC_AVAILABLE = True
except ImportError:
    MESHTASTIC_AVAILABLE = False
    pub = None

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
        position_cache=None,  # Optional PositionCache to use instead of internal dict
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
        # Use provided PositionCache if available, otherwise use simple dict for backward compatibility
        self.position_cache = position_cache
        self._use_position_cache = position_cache is not None
        if not self._use_position_cache:
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
            
            # Check if device is T-Echo and configure GPS broadcast if needed
            self._configure_techo_gps()
            
            return True
        except Exception as e:
            logger.error(f"Failed to connect to {self.port}: {e}")
            self.interface = None
            return False

    def _configure_techo_gps(self):
        """Configure GPS broadcast interval for T-Echo devices."""
        try:
            # Get device info to detect T-Echo
            node_info = self.interface.getMyNodeInfo()
            hardware = node_info.get("hardware", "")
            
            # Check if it's a T-Echo (Lilygo T-Echo)
            # T-Echo devices typically have "TECHO" or "t-echo" in hardware/model
            is_techo = (
                "techo" in str(hardware).lower() or
                "t-echo" in str(hardware).lower() or
                "lilygo" in str(hardware).lower()
            )
            
            if not is_techo:
                # Also check pio_env which might contain device info
                pio_env = node_info.get("pio_env", "")
                is_techo = "techo" in str(pio_env).lower() or "t-echo" in str(pio_env).lower()
            
            if is_techo:
                logger.info("T-Echo device detected, configuring GPS broadcast interval to 60 seconds")
                try:
                    # Get local node configuration
                    local_node = self.interface.getNode("^local")
                    
                    # Configure position broadcast interval to 60 seconds (minimum)
                    # This is the interval at which position updates are broadcast
                    if hasattr(local_node, "localConfig") and hasattr(local_node.localConfig, "position"):
                        # Set position broadcast interval to 60 seconds
                        local_node.localConfig.position.position_broadcast_secs = 60
                        local_node.writeConfig("position")
                        logger.info("Configured T-Echo GPS broadcast interval to 60 seconds")
                    else:
                        logger.warning("Could not access position config, skipping GPS configuration")
                except Exception as e:
                    logger.warning(f"Failed to configure T-Echo GPS settings: {e}")
            else:
                logger.debug(f"Device is not T-Echo (hardware: {hardware}), skipping GPS configuration")
        except Exception as e:
            logger.debug(f"Could not detect device type or configure GPS: {e}")

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

        # Subscribe to receive messages using pubsub
        # meshtastic-python publishes decoded text messages to meshtastic.receive.text
        # and position messages to meshtastic.receive.position
        pub.subscribe(self._on_receive_text, "meshtastic.receive.text")
        pub.subscribe(self._on_receive_position, "meshtastic.receive.position")

        logger.info("Meshtastic serial reader started")

    def stop(self):
        """Stop message listener."""
        self.running = False
        # Unsubscribe from messages
        if pub:
            pub.unsubscribe(self._on_receive_text, "meshtastic.receive.text")
            pub.unsubscribe(self._on_receive_position, "meshtastic.receive.position")
        self.disconnect()

    def _on_receive_text(self, packet, interface):
        """Handle received text message from Meshtastic."""
        if not self.running or not self.message_callback:
            return

        try:
            # meshtastic.receive.text provides decoded text messages
            decoded = packet.get("decoded", {})
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
            if self._use_position_cache:
                # Use PositionCache API
                pos = self.position_cache.get(node_id)
                lat = pos.lat if pos else None
                lon = pos.lon if pos else None
            else:
                # Use simple dict cache (backward compatibility)
                position = self.position_cache.get(node_id, {})
                lat = position.get("lat")
                lon = position.get("lon")

            # Try to get device uptime from node info
            device_uptime = None
            try:
                if self.interface:
                    node_info = self.interface.nodes.get(node_id)
                    if node_info:
                        # Check for device metrics with uptime
                        device_metrics = node_info.get("deviceMetrics")
                        if device_metrics:
                            device_uptime = device_metrics.get("uptimeSeconds")
            except Exception as e:
                logger.debug(f"Could not get device uptime for {node_id}: {e}")

            logger.info(f"Received message from {node_id}: {text[:50]}...")

            # Call callback with message data
            self.message_callback({
                "node_id": node_id,
                "lat": lat,
                "lon": lon,
                "text": text,
                "timestamp": time.time(),
                "device_uptime": device_uptime,  # Seconds since device boot
            })

        except Exception as e:
            logger.error(f"Error processing text message: {e}")

    def _on_receive_position(self, packet, interface):
        """Handle received position update from Meshtastic."""
        if not self.running:
            return

        try:
            # meshtastic.receive.position provides decoded position messages
            decoded = packet.get("decoded", {})
            position_data = decoded.get("position", {})
            from_node = packet.get("from")
            
            if not from_node or not position_data:
                return

            # Convert node number to string format
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
                    if self._use_position_cache:
                        # Use PositionCache API
                        self.position_cache.update(node_id, lat, lon)
                    else:
                        # Use simple dict cache (backward compatibility)
                        self.position_cache[node_id] = {
                            "lat": lat,
                            "lon": lon,
                            "timestamp": time.time(),
                        }
                
                logger.debug(f"Updated position for {node_id}: {lat}, {lon}")

        except Exception as e:
            logger.error(f"Error processing position message: {e}")

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
