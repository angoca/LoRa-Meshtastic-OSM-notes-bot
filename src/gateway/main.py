"""Main gateway application."""

import os
import sys
import time
import signal
import logging
import threading
import subprocess
from datetime import datetime, timedelta

from .config import (
    TZ,
    WORKER_INTERVAL,
    DAILY_BROADCAST_ENABLED,
    LOG_LEVEL,
)
from .database import Database
from .position_cache import PositionCache
from .meshtastic_serial import MeshtasticSerial
from .commands import CommandProcessor, MSG_DAILY_BROADCAST
from .i18n import _
from .osm_worker import OSMWorker
from .notifications import NotificationManager

# Set timezone
os.environ["TZ"] = TZ
time.tzset()

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Configure meshtastic library logging level
# Set meshtastic loggers to WARNING to reduce noise (they use DEBUG by default)
meshtastic_log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
# If LOG_LEVEL is INFO or higher, set meshtastic to WARNING to reduce verbose output
if meshtastic_log_level <= logging.INFO:
    meshtastic_log_level = logging.WARNING
logging.getLogger("meshtastic").setLevel(meshtastic_log_level)

logger = logging.getLogger(__name__)


class Gateway:
    """
    Main gateway application orchestrating all components.

    Coordinates Meshtastic serial communication, command processing,
    OSM API integration, and notifications. Runs background workers
    for queue processing and handles graceful shutdown.

    Components:
        - Database: SQLite persistence
        - PositionCache: GPS position cache
        - MeshtasticSerial: Serial communication
        - CommandProcessor: Command/message processing
        - OSMWorker: OSM API integration
        - NotificationManager: DM notifications

    Threads:
        - Main thread: Signal handling and main loop
        - Serial read thread: Continuous message reading (daemon)
        - Worker thread: Periodic queue processing (daemon)
    """

    def __init__(self):
        self.running = False
        self.db = Database()
        # PositionCache now uses the same database for persistence
        self.position_cache = PositionCache(db=self.db)
        # Pass PositionCache to MeshtasticSerial so both use the same cache
        self.serial = MeshtasticSerial(position_cache=self.position_cache)
        self.command_processor = CommandProcessor(self.db, self.position_cache)
        self.osm_worker = OSMWorker(self.db)
        self.notifications = NotificationManager(self.serial, self.db)

        # Set up message callback
        self.serial.set_message_callback(self._handle_message)

        # Worker thread
        self.worker_thread: Optional[threading.Thread] = None

        # Track if this is the first worker cycle (to skip broadcast on startup)
        self._first_worker_cycle = True

        # Track startup timestamp for time correction
        self._startup_timestamp = time.time()
        self.db.set_startup_timestamp(self._startup_timestamp)

        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()

    def _handle_message(self, msg: dict):
        """Handle incoming message from Meshtastic."""
        node_id = msg.get("node_id")
        text = msg.get("text", "")
        lat = msg.get("lat")
        lon = msg.get("lon")
        timestamp = msg.get("timestamp")
        device_uptime = msg.get("device_uptime")  # Seconds since device boot

        if not node_id:
            logger.warning("Received message without node_id")
            return

        logger.info(f"Received message from {node_id}: {text[:50]}...")

        # Update position cache if GPS data available
        if lat is not None and lon is not None:
            self.position_cache.update(node_id, lat, lon)

        # Process message
        command_type, response = self.command_processor.process_message(
            node_id=node_id,
            text=text,
            lat=lat,
            lon=lon,
            timestamp=timestamp,
            device_uptime=device_uptime,
        )

        # Handle response
        if command_type == "ignore":
            return

        if command_type in ["osmhelp", "osmmorehelp", "osmstatus", "osmcount", "osmlist", "osmqueue", "osmlang", "osmnodes"]:
            if response:
                self.notifications.send_command_response(node_id, response)

        elif command_type == "osmnote_queued":
            if response:
                local_queue_id = response  # response is the queue_id
                # Try immediate send
                sent_note = self._try_immediate_send(local_queue_id)
                # Send appropriate ACK
                if sent_note:
                    self.notifications.send_ack(
                        node_id,
                        "success",
                        local_queue_id=local_queue_id,
                        osm_note_id=sent_note.get("id"),
                        osm_note_url=sent_note.get("url"),
                    )
                else:
                    self.notifications.send_ack(node_id, "queued", local_queue_id=local_queue_id)

        elif command_type == "osmnote_reject":
            if response:
                self.notifications.send_reject(node_id, response)

        elif command_type == "osmnote_duplicate":
            if response:
                self.notifications.send_ack(node_id, "duplicate")

        elif command_type == "osmnote_error":
            if response:
                self.notifications.send_reject(node_id, response)

    def _try_immediate_send(self, local_queue_id: str):
        """Try to send a specific note immediately if internet is available.
        Returns: dict with note info if sent, None otherwise.
        """
        try:
            # Get the specific note
            note = self.db.get_note_by_queue_id(local_queue_id)
            if not note or note["status"] != "pending":
                return None

            # Get user's preferred language for attribution
            user_locale = self.db.get_user_language(note["node_id"])

            result = self.osm_worker.send_note(
                lat=note["lat"],
                lon=note["lon"],
                text=note["text_normalized"],
                locale=user_locale,
            )

            if result:
                # Update note as sent
                self.db.update_note_sent(
                    local_queue_id=note["local_queue_id"],
                    osm_note_id=result["id"],
                    osm_note_url=result["url"],
                )
                return result

            return None
        except Exception as e:
            logger.error(f"Error in immediate send: {e}")
            return None

    def _worker_loop(self):
        """Background worker loop."""
        logger.info("Worker thread started")
        while self.running:
            try:
                # Process pending notes
                sent_count = self.osm_worker.process_pending(limit=10)
                if sent_count > 0:
                    logger.info(f"Sent {sent_count} notes to OSM")

                # Process sent notifications
                self.notifications.process_sent_notifications()

                # Process failed notifications
                self.notifications.process_failed_notifications()

                # Check and apply time correction if needed (only once)
                if not self.db.get_time_correction_applied():
                    self._check_and_apply_time_correction()

                # Daily broadcast (optional) - skip on first cycle to avoid spam on restart
                if DAILY_BROADCAST_ENABLED and not self._first_worker_cycle:
                    self._check_daily_broadcast()

                # Mark that we've completed the first cycle
                self._first_worker_cycle = False

            except Exception as e:
                logger.error(f"Error in worker loop: {e}")

            # Sleep
            time.sleep(WORKER_INTERVAL)

        logger.info("Worker thread stopped")

    def _is_ntp_synchronized(self) -> bool:
        """
        Check if system time is synchronized with NTP.

        Returns:
            True if NTP is synchronized, False otherwise
        """
        try:
            # Use timedatectl to check NTP synchronization status
            result = subprocess.run(
                ["timedatectl", "status"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Check for "System clock synchronized: yes" in output
                return "System clock synchronized: yes" in result.stdout
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError) as e:
            logger.debug(f"Could not check NTP status: {e}")
            return False

    def _check_and_apply_time_correction(self):
        """
        Check if NTP has synchronized and apply time correction to pending notes if needed.

        This method:
        1. Checks if NTP is synchronized
        2. If synchronized and correction not yet applied, calculates time offset
        3. Adjusts timestamps of pending notes (not sent notes)
        4. Marks correction as applied
        """
        if not self._is_ntp_synchronized():
            logger.debug("NTP not synchronized yet, skipping time correction")
            return

        # Get startup timestamp from database
        startup_ts = self.db.get_startup_timestamp()
        if not startup_ts:
            logger.debug("No startup timestamp found, skipping time correction")
            return

        # Calculate time offset
        current_time = time.time()
        time_offset = current_time - startup_ts

        # Only apply correction if offset is significant (> 60 seconds)
        # Small offsets (< 60s) are normal and don't need correction
        if abs(time_offset) < 60:
            logger.debug(f"Time offset is small ({time_offset:.1f}s), no correction needed")
            self.db.set_time_correction_applied(True)
            return

        logger.info(f"Detected time offset: {time_offset:.1f} seconds. Applying correction to pending notes...")

        # Adjust timestamps of pending notes
        adjusted_count = self.db.adjust_pending_notes_timestamps(time_offset)

        if adjusted_count > 0:
            logger.info(f"Time correction applied: adjusted {adjusted_count} pending notes by {time_offset:.1f} seconds")
        else:
            logger.debug("No pending notes to adjust")

        # Mark correction as applied
        self.db.set_time_correction_applied(True)

    def _check_daily_broadcast(self):
        """Check if daily broadcast should be sent (once per calendar day, persisted across restarts)."""
        # Check if interface is connected before attempting broadcast
        if not self.serial.is_connected():
            logger.debug("Meshtastic interface not connected, skipping daily broadcast")
            return

        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        # Check if we already sent a broadcast today
        last_broadcast_date = self.db.get_last_broadcast_date()
        if last_broadcast_date == today_str:
            logger.debug(f"Daily broadcast already sent today ({today_str}), skipping")
            return

        # Send broadcast
        from .i18n import get_current_locale
        broadcast_msg = MSG_DAILY_BROADCAST(get_current_locale())
        if self.serial.send_broadcast(broadcast_msg):
            # Save today's date to database
            self.db.set_last_broadcast_date(today_str)
            logger.info(f"Sent daily broadcast for {today_str}")
        else:
            logger.warning("Failed to send daily broadcast (send_broadcast returned False)")

    def start(self):
        """Start the gateway."""
        logger.info("Starting Meshtastic → OSM Notes Gateway")
        logger.info(f"Timezone: {TZ}")
        logger.info(f"Database: {self.db.db_path}")

        self.running = True

        # Start serial connection
        self.serial.start()

        # Start worker thread
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

        logger.info("Gateway started")

        # Main loop
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.stop()

    def stop(self):
        """Stop the gateway."""
        if not self.running:
            return

        logger.info("Stopping gateway...")
        self.running = False

        # Stop serial
        self.serial.stop()

        # Wait for worker thread
        if self.worker_thread:
            self.worker_thread.join(timeout=5.0)

        logger.info("Gateway stopped")


def main():
    """Main entry point."""
    gateway = Gateway()
    gateway.start()


if __name__ == "__main__":
    main()


from typing import Optional
