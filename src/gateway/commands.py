"""Command processing and message templates."""

import re
import logging
from typing import Optional, Tuple
from datetime import datetime

from .config import (
    POS_GOOD, POS_MAX, DEDUP_TIME_BUCKET_SECONDS,
    MESHTASTIC_MAX_MESSAGE_LENGTH,
    DEVICE_UPTIME_RECENT, DEVICE_UPTIME_GPS_WAIT,
    GPS_VALIDATION_DISABLED,
)
from .database import Database
from .position_cache import PositionCache
from .rate_limiter import RateLimiter
from .geocoding import GeocodingService

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
    "{location}\n"
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

MSG_REJECT_NO_GPS_RECENT_START = (
    "❌ El dispositivo se prendió hace poco, por lo que la posición no es precisa.\n"
    "Espera {wait_time} segundos más para que el GPS se estabilice y reenvía.\n"
    "⚠️ No envíes datos personales ni emergencias médicas."
)

MSG_REJECT_INVALID_COORDS = (
    "❌ Las coordenadas GPS recibidas son inválidas.\n"
    "Verifica que el GPS esté funcionando correctamente.\n"
    "⚠️ No envíes datos personales ni emergencias médicas."
)

MSG_REJECT_MESSAGE_TOO_LONG = (
    "❌ El mensaje es demasiado largo (máximo {max_len} caracteres).\n"
    "Acorta el mensaje y reenvía.\n"
    "⚠️ No envíes datos personales ni emergencias médicas."
)

MSG_REJECT_STALE_GPS = (
    "❌ Reporte recibido, pero la última posición es muy vieja (>2 min).\n"
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
    "Usa #osmstatus para ver estado.\n\n"
    "📱 Configuración T‑Echo recomendada:\n"
    "• Position Broadcast: 60 segundos (mínimo)\n"
    "• Smart Broadcast Min Interval: 15 segundos\n"
    "• Smart Broadcast Min Distance: 100 metros\n"
    "• Device GPS Update: 120 segundos (2 min)\n\n"
    "Configura desde la app Meshtastic:\n"
    "Radio → Position → Position Broadcast Interval: 60\n"
    "Radio → Position → Smart Broadcast Min Interval: 15\n"
    "Radio → Position → Smart Broadcast Min Distance: 100\n"
    "Device → GPS → Update Interval: 120\n\n"
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
        self.rate_limiter = RateLimiter()
        self.geocoding = GeocodingService()

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
        device_uptime: Optional[float] = None,
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
            # Check rate limit first
            allowed, rate_limit_msg = self.rate_limiter.check_rate_limit(node_id)
            if not allowed:
                return "osmnote_reject", rate_limit_msg
            
            return self._handle_osmnote(node_id, osmnote_text, timestamp, device_uptime)

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

    def _validate_coordinates(self, lat: float, lon: float) -> Tuple[bool, Optional[str]]:
        """
        Validate GPS coordinates.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for invalid coordinates (0,0 is often a default/error value)
        if lat == 0.0 and lon == 0.0:
            return False, MSG_REJECT_INVALID_COORDS
        
        # Check valid ranges
        if not (-90 <= lat <= 90):
            return False, MSG_REJECT_INVALID_COORDS
        
        if not (-180 <= lon <= 180):
            return False, MSG_REJECT_INVALID_COORDS
        
        return True, None

    def _handle_osmnote(
        self,
        node_id: str,
        text: str,
        timestamp: Optional[float],
        device_uptime: Optional[float] = None,
    ) -> Tuple[str, Optional[str]]:
        """Handle #osmnote command."""
        import time

        # Check message length
        if len(text) > MESHTASTIC_MAX_MESSAGE_LENGTH:
            return "osmnote_reject", MSG_REJECT_MESSAGE_TOO_LONG.format(
                max_len=MESHTASTIC_MAX_MESSAGE_LENGTH
            )

        # Check if text is empty (only hashtag)
        if not text or not text.strip():
            return "osmnote_reject", MSG_FALTA_TEXTO

        text_normalized = self.normalize_text(text)

        # Get position from cache
        position = self.position_cache.get(node_id)
        
        # If GPS validation is disabled, use a default position (Bogotá center)
        if GPS_VALIDATION_DISABLED:
            if not position:
                # Use default position for Bogotá if no GPS available
                default_lat = 4.6097
                default_lon = -74.0817
                logger.warning(f"GPS validation disabled - using default position for {node_id}: ({default_lat}, {default_lon})")
                # Create a temporary position object
                from .position_cache import Position
                position = Position(
                    lat=default_lat,
                    lon=default_lon,
                    received_at=time.time(),
                    seen_count=1
                )
            # Skip GPS validation checks
            lat = position.lat
            lon = position.lon
        else:
            # Normal GPS validation flow
            if not position:
                # Check if device was recently started
                if device_uptime is not None and device_uptime < DEVICE_UPTIME_RECENT:
                    wait_time = int(DEVICE_UPTIME_GPS_WAIT - device_uptime)
                    if wait_time > 0:
                        return "osmnote_reject", MSG_REJECT_NO_GPS_RECENT_START.format(
                            wait_time=wait_time
                        )
                return "osmnote_reject", MSG_REJECT_NO_GPS

            # Validate coordinates
            is_valid, error_msg = self._validate_coordinates(position.lat, position.lon)
            if not is_valid:
                return "osmnote_reject", error_msg

            # Check position age
            pos_age = self.position_cache.get_age(node_id)
            if pos_age is None or pos_age > POS_MAX:
                # Check if device was recently started
                if device_uptime is not None and device_uptime < DEVICE_UPTIME_RECENT:
                    wait_time = int(DEVICE_UPTIME_GPS_WAIT - device_uptime)
                    if wait_time > 0:
                        return "osmnote_reject", MSG_REJECT_NO_GPS_RECENT_START.format(
                            wait_time=wait_time
                        )
                return "osmnote_reject", MSG_REJECT_STALE_GPS

        # Determine if position is approximate (only if GPS validation is enabled)
        is_approximate = False
        if not GPS_VALIDATION_DISABLED:
            pos_age = self.position_cache.get_age(node_id)
            if pos_age is not None:
                is_approximate = POS_GOOD < pos_age <= POS_MAX
        
        if is_approximate:
            text_normalized = f"[posición aproximada] {text_normalized}"

        # Check for duplicates
        recv_time = timestamp or time.time()
        time_bucket = int(recv_time / DEDUP_TIME_BUCKET_SECONDS)

        if self.db.check_duplicate(
            node_id,
            text_normalized,
            lat,
            lon,
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
