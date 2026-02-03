"""Command processing and message templates."""

import re
import logging
from typing import Optional, Tuple
from datetime import datetime

from .config import POS_GOOD, POS_MAX, DEDUP_TIME_BUCKET_SECONDS
from .database import Database
from .position_cache import PositionCache

logger = logging.getLogger(__name__)


# Message templates
MSG_FALTA_TEXTO = (
    "❌ Falta el texto del reporte.\n"
    "Usa: #osmnote <tu mensaje>\n"
    "⚠️ No envíes datos personales ni emergencias médicas."
)

MSG_ACK_SUCCESS = (
    "✅ Reporte recibido y nota creada en OSM.\n"
    "📝 Nota: #{id}\n"
    "{url}\n"
    "⚠️ No envíes datos personales ni emergencias médicas."
)

MSG_ACK_QUEUED = (
    "✅ Reporte recibido. Quedó en cola para enviar cuando haya Internet.\n"
    "📦 En cola: {queue_id}\n"
    "⚠️ No envíes datos personales ni emergencias médicas."
)

MSG_REJECT_NO_GPS = (
    "❌ Reporte recibido, pero no hay GPS reciente del dispositivo.\n"
    "Mantén el T‑Echo encendido al aire libre 30–60 s y reenvía.\n"
    "⚠️ No envíes datos personales ni emergencias médicas."
)

MSG_REJECT_STALE_GPS = (
    "❌ Reporte recibido, pero la última posición es muy vieja (>60 s).\n"
    "Espera a que el GPS se actualice y reenvía.\n"
    "⚠️ No envíes datos personales ni emergencias médicas."
)

MSG_DUPLICATE = (
    "✅ Reporte recibido (ya estaba registrado).\n"
    "⚠️ No envíes datos personales ni emergencias médicas."
)

MSG_HELP = (
    "ℹ️ Para crear una nota de mapeo escribe:\n"
    "#osmnote <tu mensaje>\n\n"
    "Usa #osmstatus para ver estado.\n"
    "⚠️ No envíes datos personales ni emergencias médicas."
)

MSG_Q_TO_NOTE = (
    "✅ Enviado desde cola: {queue_id} → Nota OSM #{note_id}\n"
    "{url}"
)

MSG_DAILY_BROADCAST = (
    "ℹ️ Gateway de notas OSM activo.\n"
    "Usa:\n"
    "#osmnote <mensaje>\n"
    "#osmhelp"
)


class CommandProcessor:
    """Process Meshtastic commands and messages."""

    # Hashtag variants for osmnote
    OSMNOTE_VARIANTS = [
        r"#osmnote\b",
        r"#osm-note\b",
        r"#osm_note\b",
    ]

    def __init__(self, db: Database, position_cache: PositionCache):
        self.db = db
        self.position_cache = position_cache

    def normalize_text(self, text: str) -> str:
        """Normalize text for deduplication."""
        # Trim and collapse whitespace
        text = " ".join(text.strip().split())
        return text

    def extract_osmnote(self, text: str) -> Optional[str]:
        """
        Extract osmnote command and return remaining text.
        
        Uses regex with word boundaries to ensure the hashtag is a complete word,
        preventing false matches like '#osmnotetest' from being treated as '#osmnote'.
        
        Args:
            text: Input text that may contain #osmnote command
            
        Returns:
            Remaining text after removing the hashtag, or None if no valid match found
        """
        for variant in self.OSMNOTE_VARIANTS:
            # Use regex search to check for match with word boundaries
            match = re.search(variant, text, flags=re.IGNORECASE)
            if match:
                # Remove the hashtag and return remaining text
                remaining = re.sub(
                    variant,
                    "",
                    text,
                    flags=re.IGNORECASE,
                ).strip()
                return remaining
        return None

    def process_message(
        self,
        node_id: str,
        text: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        timestamp: Optional[float] = None,
    ) -> Tuple[str, Optional[str]]:
        """
        Process incoming message and return command type and response.
        
        Updates position cache if GPS data is provided. Processes commands
        and creates notes for #osmnote reports.
        
        Args:
            node_id: Meshtastic node ID sending the message
            text: Message text content
            lat: Optional latitude (updates position cache)
            lon: Optional longitude (updates position cache)
            timestamp: Optional message timestamp (defaults to current time)
            
        Returns:
            Tuple of (command_type, response_message):
            - command_type: One of 'osmnote', 'osmnote_queued', 'osmnote_reject',
              'osmnote_duplicate', 'osmhelp', 'osmstatus', 'osmcount', 'osmlist',
              'osmqueue', 'ignore'
            - response_message: Response text for commands, queue_id for osmnote_queued,
              or None for ignored messages
              
        Examples:
            >>> processor.process_message("node1", "#osmhelp")
            ('osmhelp', 'ℹ️ Para crear una nota...')
            
            >>> processor.process_message("node1", "#osmnote test", lat=1.0, lon=2.0)
            ('osmnote_queued', 'Q-0001')
        """
        if not text or not text.strip():
            return "ignore", None

        text = text.strip()
        text_lower = text.lower()

        # Update position cache if GPS data available
        if lat is not None and lon is not None:
            self.position_cache.update(node_id, lat, lon)

        # Check for commands
        if text_lower == "#osmhelp":
            return "osmhelp", MSG_HELP

        if text_lower == "#osmstatus":
            return self._handle_status(node_id)

        if text_lower.startswith("#osmcount"):
            _, count_msg = self._handle_count(node_id)
            return "osmcount", count_msg

        if text_lower.startswith("#osmlist"):
            return self._handle_list(node_id, text)

        if text_lower == "#osmqueue":
            _, queue_msg = self._handle_queue(node_id)
            return "osmqueue", queue_msg

        # Check for osmnote
        osmnote_text = self.extract_osmnote(text)
        if osmnote_text is not None:
            return self._handle_osmnote(node_id, osmnote_text, timestamp)

        # Ignore other messages
        return "ignore", None

    def _handle_status(self, node_id: str) -> Tuple[str, str]:
        """Handle #osmstatus command."""
        import requests
        internet_ok = False
        try:
            response = requests.get("https://www.google.com", timeout=3)
            internet_ok = response.status_code == 200
        except:
            pass

        total_queue = self.db.get_total_queue_size()
        node_stats = self.db.get_node_stats(node_id)
        node_queue = node_stats["queue"]

        status_msg = (
            f"ℹ️ Gateway activo\n"
            f"Internet: {'✅ OK' if internet_ok else '❌ NO'}\n"
            f"Cola total: {total_queue}\n"
            f"Tu cola: {node_queue}"
        )
        return "osmstatus", status_msg

    def _handle_count(self, node_id: str) -> Tuple[str, str]:
        """Handle #osmcount command."""
        stats = self.db.get_node_stats(node_id)
        count_msg = (
            f"📊 Notas creadas:\n"
            f"Hoy: {stats['today']}\n"
            f"Total: {stats['total']}"
        )
        return "osmcount", count_msg

    def _handle_list(self, node_id: str, text: str) -> Tuple[str, str]:
        """Handle #osmlist [n] command."""
        # Extract number
        parts = text.split()
        limit = 5
        if len(parts) > 1:
            try:
                limit = int(parts[1])
                limit = min(max(limit, 1), 20)  # Clamp between 1 and 20
            except ValueError:
                pass

        notes = self.db.get_node_notes(node_id, limit=limit, include_pending=True)
        if not notes:
            return "osmlist", "📝 No hay notas registradas."

        lines = [f"📝 Últimas {len(notes)} notas:"]
        for note in notes:
            status_icon = "⏳" if note["status"] == "pending" else "✅"
            created = datetime.fromisoformat(note["created_at"]).strftime("%Y-%m-%d %H:%M")
            text_preview = note["text_original"][:30] + "..." if len(note["text_original"]) > 30 else note["text_original"]
            if note["status"] == "sent" and note["osm_note_url"]:
                lines.append(f"{status_icon} {created}: {text_preview} → {note['osm_note_url']}")
            else:
                lines.append(f"{status_icon} {created}: {text_preview} [{note['local_queue_id']}]")

        return "osmlist", "\n".join(lines)

    def _handle_queue(self, node_id: str) -> Tuple[str, str]:
        """Handle #osmqueue command."""
        total_queue = self.db.get_total_queue_size()
        node_stats = self.db.get_node_stats(node_id)
        node_queue = node_stats["queue"]

        queue_msg = (
            f"📦 Cola:\n"
            f"Total: {total_queue}\n"
            f"Tu cola: {node_queue}"
        )
        return "osmqueue", queue_msg

    def _handle_osmnote(
        self,
        node_id: str,
        text: str,
        timestamp: Optional[float],
    ) -> Tuple[str, Optional[str]]:
        """Handle #osmnote command."""
        import time

        # Check if text is empty (only hashtag)
        if not text or not text.strip():
            return "osmnote_reject", MSG_FALTA_TEXTO

        text_normalized = self.normalize_text(text)

        # Get position from cache
        position = self.position_cache.get(node_id)
        if not position:
            return "osmnote_reject", MSG_REJECT_NO_GPS

        # Check position age
        pos_age = self.position_cache.get_age(node_id)
        if pos_age is None or pos_age > POS_MAX:
            return "osmnote_reject", MSG_REJECT_STALE_GPS

        # Determine if position is approximate
        is_approximate = POS_GOOD < pos_age <= POS_MAX
        if is_approximate:
            text_normalized = f"[posición aproximada] {text_normalized}"

        # Check for duplicates
        recv_time = timestamp or time.time()
        time_bucket = int(recv_time / DEDUP_TIME_BUCKET_SECONDS)

        if self.db.check_duplicate(
            node_id,
            text_normalized,
            position.lat,
            position.lon,
            time_bucket,
        ):
            return "osmnote_duplicate", MSG_DUPLICATE

        # Create note
        local_queue_id = self.db.create_note(
            node_id=node_id,
            lat=position.lat,
            lon=position.lon,
            text_original=text,
            text_normalized=text_normalized,
        )

        if not local_queue_id:
            return "osmnote_error", "❌ Error al crear nota."

        # Return queued status with queue_id for extraction
        return "osmnote_queued", local_queue_id
