"""Notification system for DM messages."""

import time
import logging
from typing import Dict, List, Optional
from collections import defaultdict
from datetime import datetime

from .config import (
    DRY_RUN,
    NOTIFICATION_ANTI_SPAM_WINDOW,
    NOTIFICATION_ANTI_SPAM_MAX,
)
from .database import Database
from .commands import MSG_ACK_SUCCESS, MSG_ACK_QUEUED, MSG_Q_TO_NOTE
from .meshtastic_serial import MeshtasticSerial

logger = logging.getLogger(__name__)


class NotificationManager:
    """Manage DM notifications with anti-spam."""

    def __init__(self, serial: MeshtasticSerial, db: Database):
        self.serial = serial
        self.db = db
        self.node_notification_times: Dict[str, List[float]] = defaultdict(list)

    def send_ack(
        self,
        node_id: str,
        status: str,
        local_queue_id: Optional[str] = None,
        osm_note_id: Optional[int] = None,
        osm_note_url: Optional[str] = None,
    ):
        """
        Send acknowledgment DM to a node.
        
        Sends different messages based on status. Implements anti-spam
        to prevent flooding nodes with notifications.
        
        Args:
            node_id: Target Meshtastic node ID
            status: ACK status - one of:
                - 'success': Note created in OSM (requires osm_note_id and osm_note_url)
                - 'queued': Note queued for sending (requires local_queue_id)
                - 'duplicate': Duplicate note detected
            local_queue_id: Queue ID for queued status (e.g., "Q-0001")
            osm_note_id: OSM note ID for success status
            osm_note_url: OSM note URL for success status
            
        Note:
            Respects anti-spam limits (max 3 notifications per minute per node).
            In DRY_RUN mode, logs instead of sending.
        """
        if DRY_RUN:
            logger.info(f"[DRY_RUN] Would send ACK to {node_id}: {status}")
            return

        if status == "success" and osm_note_id and osm_note_url:
            message = MSG_ACK_SUCCESS.format(id=osm_note_id, url=osm_note_url)
        elif status == "queued" and local_queue_id:
            message = MSG_ACK_QUEUED.format(queue_id=local_queue_id)
        elif status == "reject":
            # Message should be passed separately
            return
        elif status == "duplicate":
            from .commands import MSG_DUPLICATE
            message = MSG_DUPLICATE
        else:
            logger.warning(f"Unknown ACK status: {status}")
            return

        self._send_dm_with_antispam(node_id, message)

    def send_reject(self, node_id: str, message: str):
        """Send rejection message."""
        if DRY_RUN:
            logger.info(f"[DRY_RUN] Would send reject to {node_id}: {message[:50]}...")
            return

        self._send_dm_with_antispam(node_id, message)

    def send_command_response(self, node_id: str, message: str):
        """Send command response."""
        if DRY_RUN:
            logger.info(f"[DRY_RUN] Would send command response to {node_id}: {message[:50]}...")
            return

        self._send_dm_with_antispam(node_id, message)

    def process_sent_notifications(self):
        """Process pending sent notifications (Q→Note)."""
        pending = self.db.get_pending_for_notification()
        if not pending:
            return

        # Group by node_id for anti-spam
        node_notes: Dict[str, List[Dict]] = defaultdict(list)
        for note in pending:
            node_notes[note["node_id"]].append(note)

        for node_id, notes in node_notes.items():
            # Check anti-spam
            if self._check_antispam(node_id):
                # Send summary instead
                self._send_summary(node_id, len(notes))
            else:
                # Send individual notifications
                for note in notes[:NOTIFICATION_ANTI_SPAM_MAX]:
                    message = MSG_Q_TO_NOTE.format(
                        queue_id=note["local_queue_id"],
                        note_id=note["osm_note_id"],
                        url=note["osm_note_url"],
                    )
                    if self.serial.send_dm(node_id, message):
                        self.db.mark_notified_sent(note["local_queue_id"])
                        self._record_notification(node_id)

    def _send_dm_with_antispam(self, node_id: str, message: str):
        """Send DM with anti-spam check."""
        if self._check_antispam(node_id):
            logger.debug(f"Anti-spam: skipping DM to {node_id}")
            return

        if self.serial.send_dm(node_id, message):
            self._record_notification(node_id)

    def _check_antispam(self, node_id: str) -> bool:
        """Check if node has exceeded anti-spam limit."""
        now = time.time()
        times = self.node_notification_times[node_id]

        # Remove old entries
        cutoff = now - NOTIFICATION_ANTI_SPAM_WINDOW
        times[:] = [t for t in times if t > cutoff]

        return len(times) >= NOTIFICATION_ANTI_SPAM_MAX

    def _record_notification(self, node_id: str):
        """Record notification timestamp."""
        self.node_notification_times[node_id].append(time.time())

    def _send_summary(self, node_id: str, count: int):
        """Send summary message when anti-spam triggered."""
        message = (
            f"✅ Se enviaron {count} reportes en cola. "
            "Usa #osmlist para ver detalles."
        )
        if self.serial.send_dm(node_id, message):
            # Mark all as notified
            pending = self.db.get_pending_for_notification()
            for note in pending:
                if note["node_id"] == node_id:
                    self.db.mark_notified_sent(note["local_queue_id"])
