"""Meshtastic serial communication."""

import serial
import logging
import time
import threading
from typing import Optional, Callable, Dict, Any
from queue import Queue

from .config import SERIAL_PORT

logger = logging.getLogger(__name__)


class MeshtasticSerial:
    """
    Meshtastic serial connection with auto-reconnect.
    
    Manages USB serial communication with Meshtastic devices. Handles
    connection, reconnection, message parsing, and sending DMs/broadcasts.
    
    Attributes:
        port: Serial port path (e.g., "/dev/ttyACM0")
        baudrate: Serial baudrate (default: 9600)
        timeout: Read timeout in seconds
        serial_conn: pyserial Serial object (None if not connected)
        running: Flag indicating if reader thread is running
        message_callback: Callback function for incoming messages
        
    Note:
        Uses a separate thread for reading messages. Supports auto-reconnect
        on connection loss. Message format is simplified for MVP (JSON or
        pipe-separated text).
    """

    def __init__(
        self,
        port: str = SERIAL_PORT,
        baudrate: int = 9600,
        timeout: float = 1.0,
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn: Optional[serial.Serial] = None
        self.running = False
        self.reconnect_delay = 5.0
        self.message_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self.read_thread: Optional[threading.Thread] = None
        self.write_queue: Queue = Queue()

    def set_message_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback for incoming messages."""
        self.message_callback = callback

    def connect(self) -> bool:
        """Connect to serial port."""
        try:
            if self.serial_conn and self.serial_conn.is_open:
                return True

            logger.info(f"Connecting to {self.port} at {self.baudrate} baud...")
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            )
            logger.info(f"Connected to {self.port}")
            return True
        except serial.SerialException as e:
            logger.error(f"Failed to connect to {self.port}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting: {e}")
            return False

    def disconnect(self):
        """Disconnect from serial port."""
        self.running = False
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logger.info("Disconnected from serial port")

    def start(self):
        """Start reading thread."""
        if self.running:
            return

        if not self.connect():
            logger.error("Failed to connect, cannot start")
            return

        self.running = True
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()
        logger.info("Meshtastic serial reader started")

    def stop(self):
        """Stop reading thread."""
        self.running = False
        if self.read_thread:
            self.read_thread.join(timeout=2.0)
        self.disconnect()

    def _read_loop(self):
        """Main read loop with auto-reconnect."""
        buffer = b""
        while self.running:
            try:
                if not self.serial_conn or not self.serial_conn.is_open:
                    if not self.connect():
                        time.sleep(self.reconnect_delay)
                        continue

                # Read available data
                if self.serial_conn.in_waiting > 0:
                    data = self.serial_conn.read(self.serial_conn.in_waiting)
                    buffer += data

                    # Try to parse messages (simplified - Meshtastic uses protobuf)
                    # For MVP, we'll parse text-based messages
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        line = line.strip()
                        if line:
                            self._parse_message(line)

                time.sleep(0.1)  # Small delay to avoid busy waiting

            except serial.SerialException as e:
                logger.error(f"Serial error: {e}, reconnecting...")
                if self.serial_conn:
                    try:
                        self.serial_conn.close()
                    except:
                        pass
                self.serial_conn = None
                time.sleep(self.reconnect_delay)

            except Exception as e:
                logger.error(f"Unexpected error in read loop: {e}")
                time.sleep(1.0)

    def _parse_message(self, data: bytes):
        """Parse incoming message (simplified parser for MVP).
        
        Expected formats:
        1. JSON: {"from": "node_id", "lat": 1.23, "lon": 4.56, "text": "message"}
        2. Pipe-separated: "node_id|lat|lon|message" or "node_id|||message"
        
        Note: In production, Meshtastic uses protobuf packets. This MVP uses
        a simplified text-based protocol. For full Meshtastic integration,
        use the meshtastic-python library to parse protobuf packets.
        """
        try:
            # For MVP, we'll use a simple text-based protocol
            # In production, this would parse Meshtastic protobuf packets
            text = data.decode("utf-8", errors="ignore")
            
            # Simple format: "NODE_ID|LAT|LON|MESSAGE" or "NODE_ID|||MESSAGE"
            # Or JSON-like: {"from": "node_id", "lat": 1.23, "lon": 4.56, "text": "message"}
            if text.startswith("{"):
                import json
                msg = json.loads(text)
                node_id = str(msg.get("from", ""))
                lat = msg.get("lat")
                lon = msg.get("lon")
                message_text = msg.get("text", "")
            else:
                # Fallback: pipe-separated format
                parts = text.split("|", 3)
                if len(parts) >= 2:
                    node_id = parts[0]
                    try:
                        lat = float(parts[1]) if parts[1] else None
                        lon = float(parts[2]) if len(parts) > 2 and parts[2] else None
                    except ValueError:
                        lat = None
                        lon = None
                    message_text = parts[3] if len(parts) > 3 else ""
                else:
                    return

            if self.message_callback:
                self.message_callback({
                    "node_id": node_id,
                    "lat": lat,
                    "lon": lon,
                    "text": message_text,
                    "timestamp": time.time(),
                })

        except Exception as e:
            logger.debug(f"Failed to parse message: {e}")

    def send_dm(self, node_id: str, message: str) -> bool:
        """Send direct message to a node."""
        if not self.serial_conn or not self.serial_conn.is_open:
            logger.warning("Serial not connected, cannot send DM")
            return False

        try:
            # Format: DM|NODE_ID|MESSAGE
            cmd = f"DM|{node_id}|{message}\n"
            self.serial_conn.write(cmd.encode("utf-8"))
            logger.info(f"Sent DM to {node_id}: {message[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to send DM: {e}")
            return False

    def send_broadcast(self, message: str) -> bool:
        """Send broadcast message."""
        if not self.serial_conn or not self.serial_conn.is_open:
            logger.warning("Serial not connected, cannot send broadcast")
            return False

        try:
            # Format: BC|MESSAGE
            cmd = f"BC|{message}\n"
            self.serial_conn.write(cmd.encode("utf-8"))
            logger.info(f"Sent broadcast: {message[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to send broadcast: {e}")
            return False
