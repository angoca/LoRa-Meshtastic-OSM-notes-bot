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
from .i18n import _, get_current_locale

logger = logging.getLogger(__name__)


# Message template functions (translated)
def MSG_FALTA_TEXTO(locale: Optional[str] = None):
    return (
        _("❌ Falta el texto del reporte.\n", locale)
        + _("Usa: #osmnote <tu mensaje>\n", locale)
        + _("⚠️ No envíes datos personales ni emergencias de cualquier tipo.", locale)
    )


def MSG_ACK_SUCCESS(id: int, url: str, location: str = "", locale: Optional[str] = None, show_warning: bool = True):
    message = (
        _("✅ Reporte recibido y nota creada en OSM.\n", locale)
        + _("📝 Nota: #{id}\n", locale).format(id=id)
        + f"{url}\n"
        + location
    )
    if show_warning:
        message += _("⚠️ No envíes datos personales ni emergencias de cualquier tipo.", locale)
    return message


def MSG_ACK_QUEUED(queue_id: str, locale: Optional[str] = None, show_warning: bool = True):
    message = (
        _("✅ Reporte recibido. Quedó en cola para enviar cuando haya Internet.\n", locale)
        + _("📦 En cola: {queue_id}\n", locale).format(queue_id=queue_id)
    )
    if show_warning:
        message += _("⚠️ No envíes datos personales ni emergencias de cualquier tipo.", locale)
    return message


def MSG_REJECT_NO_GPS(locale: Optional[str] = None):
    return (
        _("❌ Reporte recibido, pero no hay GPS reciente del dispositivo.\n", locale)
        + _("Mantén el T‑Echo encendido al aire libre 30–60 s y reenvía.\n", locale)
        + _("⚠️ No envíes datos personales ni emergencias de cualquier tipo.", locale)
    )


def MSG_REJECT_NO_GPS_RECENT_START(wait_time: int, locale: Optional[str] = None):
    return (
        _("❌ El dispositivo se prendió hace poco, por lo que la posición no es precisa.\n", locale)
        + _("Espera {wait_time} segundos más para que el GPS se estabilice y reenvía.\n", locale).format(wait_time=wait_time)
        + _("⚠️ No envíes datos personales ni emergencias de cualquier tipo.", locale)
    )


def MSG_REJECT_INVALID_COORDS(locale: Optional[str] = None):
    return (
        _("❌ Las coordenadas GPS recibidas son inválidas.\n", locale)
        + _("Verifica que el GPS esté funcionando correctamente.\n", locale)
        + _("⚠️ No envíes datos personales ni emergencias de cualquier tipo.", locale)
    )


def MSG_REJECT_MESSAGE_TOO_LONG(max_len: int, locale: Optional[str] = None):
    return (
        _("❌ El mensaje es demasiado largo (máximo {max_len} caracteres).\n", locale).format(max_len=max_len)
        + _("Acorta el mensaje y reenvía.\n", locale)
        + _("⚠️ No envíes datos personales ni emergencias de cualquier tipo.", locale)
    )


def MSG_REJECT_STALE_GPS(locale: Optional[str] = None):
    return (
        _("❌ Reporte recibido, pero la última posición es muy vieja (>2 min).\n", locale)
        + _("Espera a que el GPS se actualice y reenvía.\n", locale)
        + _("⚠️ No envíes datos personales ni emergencias de cualquier tipo.", locale)
    )


def MSG_DUPLICATE(locale: Optional[str] = None, show_warning: bool = True):
    message = _("✅ Reporte recibido (ya estaba registrado).\n", locale)
    if show_warning:
        message += _("⚠️ No envíes datos personales ni emergencias de cualquier tipo.", locale)
    return message


def MSG_HELP(locale: Optional[str] = None):
    return (
        _("ℹ️ Comandos disponibles:\n\n", locale)
        + _("• #osmnote <mensaje> - Crear nota OSM\n", locale)
        + _("• #osmstatus - Ver estado del gateway\n", locale)
        + _("• #osmcount - Ver conteo de notas\n", locale)
        + _("• #osmlist [n] - Listar últimas notas\n", locale)
        +         _("• #osmqueue - Ver tamaño de cola\n", locale)
        + _("• #osmnodes - Listar nodos en la red\n", locale)
        + _("• #osmhelp - Esta ayuda\n", locale)
        + _("• #osmmorehelp - Ayuda extendida con detalles\n\n", locale)
        + _("• #osmlang [es|en] - Cambiar idioma / Change language\n\n", locale)
        + _("💡 Consejo: Configura #osmnote en Quick Chat.\n", locale)
        + _("Mensajes → menú (3 puntos) → Quick Chat → #osmnote\n", locale)
        + _("Desactiva 'Instantly send' para que quede 'Append to message'.\n\n", locale)
        + _("📱 Configuración recomendada para dispositivos móviles:\n", locale)
        + _("Position Broadcast: 60s | Smart Broadcast: 15s/100m | GPS Update: 120s\n", locale)
        + _("Role: CLIENT (para reenviar mensajes #osmXXX)\n\n", locale)
        + _("⚠️ No envíes datos personales ni emergencias de cualquier tipo.", locale)
    )


def MSG_MORE_HELP(locale: Optional[str] = None):
    return (
        _("ℹ️ Información detallada:\n\n", locale)
        + _("📝 #osmnote <mensaje>\n", locale)
        + _("Crea una nota en OpenStreetMap con tu ubicación GPS.\n", locale)
        + _("El mensaje debe tener máximo 200 caracteres.\n", locale)
        + _("Requiere GPS activo y posición reciente (<2 min).\n\n", locale)
        + _("📊 #osmstatus\n", locale)
        + _("Muestra el estado del gateway:\n", locale)
        + _("• Si hay conexión a Internet\n", locale)
        + _("• Tamaño de la cola total\n", locale)
        + _("• Tamaño de tu cola personal\n\n", locale)
        + _("📈 #osmcount\n", locale)
        + _("Muestra cuántas notas has creado:\n", locale)
        + _("• Notas creadas hoy\n", locale)
        + _("• Total de notas creadas\n\n", locale)
        + _("📋 #osmlist [n]\n", locale)
        + _("Lista tus últimas notas creadas.\n", locale)
        + _("• Sin número: muestra las últimas 5\n", locale)
        + _("• Con número: muestra las últimas n (máximo 20)\n", locale)
        + _("• Ejemplo: #osmlist 10\n", locale)
        + _("• Muestra notas pendientes y enviadas\n\n", locale)
        + _("📦 #osmqueue\n", locale)
        + _("Muestra el tamaño de las colas:\n", locale)
        + _("• Cola total del gateway\n", locale)
        + _("• Tu cola personal\n\n", locale)
        + _("📡 #osmnodes\n", locale)
        + _("Lista todos los nodos conocidos en la red mesh.\n", locale)
        + _("Muestra:\n", locale)
        + _("• Node ID de cada dispositivo\n", locale)
        + _("• Última posición GPS conocida\n", locale)
        + _("• Tiempo desde la última vez visto\n", locale)
        + _("• Número de veces que se ha visto\n\n", locale)
        + _("Útil para validar conectividad entre dispositivos.\n\n", locale)
        + _("🌐 #osmlang [es|en]\n", locale)
        + _("Cambia el idioma de los mensajes.\n", locale)
        + _("• Sin parámetro: muestra idioma actual\n", locale)
        + _("• Con parámetro: cambia idioma (es=Español, en=English)\n\n", locale)
        + _("💡 Quick Chat (para facilitar #osmnote desde la app):\n", locale)
        + _("1. Abre la pantalla de mensajes (Conversations)\n", locale)
        + _("2. Toca el menú (3 puntos) arriba a la derecha\n", locale)
        + _("3. Selecciona 'Quick Chat'\n", locale)
        + _("4. Agrega: #osmnote\n", locale)
        + _("5. Desactiva 'Instantly send' para que quede 'Append to message'\n", locale)
        + _("6. Luego selecciona #osmnote y escribe tu reporte\n\n", locale)
        + _("Esto evita errores al escribir el hashtag.\n\n", locale)
        + _("📡 Configuración de Role (para reenvío de mensajes):\n", locale)
        + _("Para que los mensajes #osmXXX lleguen al gateway:\n", locale)
        + _("• Dispositivos móviles: Role = CLIENT\n", locale)
        + _("• Esto permite que el dispositivo reenvíe mensajes\n", locale)
        + _("• Configuración: Settings → Device → Role → CLIENT\n", locale)
        + _("• Nota: CLIENT_MUTE no reenvía mensajes\n\n", locale)
        + _("⚠️ No envíes datos personales ni emergencias de cualquier tipo.", locale)
    )


def MSG_Q_TO_NOTE(queue_id: str, note_id: int, url: str, locale: Optional[str] = None):
    return _("✅ Enviado desde cola: {queue_id} → Nota OSM #{note_id}\n", locale).format(
        queue_id=queue_id, note_id=note_id
    ) + url


def MSG_DAILY_BROADCAST(locale: Optional[str] = None):
    return (
        _("ℹ️ Gateway de notas OSM activo.\n", locale)
        + _("Usa:\n", locale)
        + "#osmnote <mensaje>\n"
        + "#osmhelp"
    )


class CommandProcessor:
    """Process Meshtastic commands and messages."""

    # Hashtag variants for osmnote
    OSMNOTE_VARIANTS = [
        r"#osmnote\b",
        r"#osmnotes\b",  # Plural variant (common typo)
        r"#osm-note\b",
        r"#osm-notes\b",  # Plural variant with hyphen
        r"#osm_note\b",
        r"#osm_notes\b",  # Plural variant with underscore
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
              'osmnote_duplicate', 'osmhelp', 'osmmorehelp', 'osmstatus', 'osmcount', 'osmlist',
              'osmqueue', 'ignore'
            - response_message: Response text for commands, queue_id for osmnote_queued,
              or None for ignored messages

        Examples:
            >>> processor.process_message("node1", "#osmhelp")
            ('osmhelp', 'ℹ️ Para crear una nota...')

            >>> processor.process_message("node1", "#osmmorehelp")
            ('osmmorehelp', 'ℹ️ Información adicional...')

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

        # Get user's preferred language
        user_lang = self.db.get_user_language(node_id)

        # Check for commands
        if text_lower == "#osmhelp":
            return "osmhelp", MSG_HELP(user_lang)

        if text_lower == "#osmmorehelp":
            return "osmmorehelp", MSG_MORE_HELP(user_lang)

        if text_lower.startswith("#osmlang"):
            return self._handle_lang(node_id, text, user_lang)

        if text_lower == "#osmstatus":
            return self._handle_status(node_id, user_lang)

        if text_lower.startswith("#osmcount"):
            _, count_msg = self._handle_count(node_id, user_lang)
            return "osmcount", count_msg

        if text_lower.startswith("#osmlist"):
            return self._handle_list(node_id, text, user_lang)

        if text_lower == "#osmqueue":
            _, queue_msg = self._handle_queue(node_id, user_lang)
            return "osmqueue", queue_msg

        if text_lower == "#osmnodes":
            return self._handle_nodes(user_lang)

        # Check for osmnote
        osmnote_text = self.extract_osmnote(text)
        if osmnote_text is not None:
            # Check rate limit first
            allowed, rate_limit_msg = self.rate_limiter.check_rate_limit(node_id, user_lang)
            if not allowed:
                return "osmnote_reject", rate_limit_msg

            return self._handle_osmnote(node_id, osmnote_text, timestamp, device_uptime, user_lang)

        # Ignore other messages
        return "ignore", None

    def _handle_status(self, node_id: str, locale: Optional[str] = None) -> Tuple[str, str]:
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
            _("ℹ️ Gateway activo\n", locale)
            + _("Internet: {status}\n", locale).format(status="✅ OK" if internet_ok else "❌ NO")
            + _("Cola total: {total}\n", locale).format(total=total_queue)
            + _("Tu cola: {queue}", locale).format(queue=node_queue)
        )
        return "osmstatus", status_msg

    def _handle_count(self, node_id: str, locale: str) -> Tuple[str, str]:
        """Handle #osmcount command."""
        from .config import TZ
        stats = self.db.get_node_stats(node_id, timezone=TZ)
        count_msg = (
            _("📊 Notas creadas:\n", locale)
            + _("Hoy: {today}\n", locale).format(today=stats['today'])
            + _("Total: {total}\n", locale).format(total=stats['total'])
            + _("Zona horaria: {tz}", locale).format(tz=stats['timezone'])
        )
        return "osmcount", count_msg

    def _handle_list(self, node_id: str, text: str, locale: Optional[str] = None) -> Tuple[str, str]:
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
            return "osmlist", _("📝 No hay notas registradas.", locale)

        lines = [_("📝 Últimas {count} notas:", locale).format(count=len(notes))]
        for note in notes:
            status_icon = "⏳" if note["status"] == "pending" else "✅"
            created = datetime.fromisoformat(note["created_at"]).strftime("%Y-%m-%d %H:%M")
            text_preview = note["text_original"][:30] + "..." if len(note["text_original"]) > 30 else note["text_original"]
            if note["status"] == "sent" and note["osm_note_url"]:
                lines.append(f"{status_icon} {created}: {text_preview} → {note['osm_note_url']}")
            else:
                lines.append(f"{status_icon} {created}: {text_preview} [{note['local_queue_id']}]")

        return "osmlist", "\n".join(lines)

    def _handle_queue(self, node_id: str, locale: str) -> Tuple[str, str]:
        """Handle #osmqueue command."""
        total_queue = self.db.get_total_queue_size()
        node_stats = self.db.get_node_stats(node_id)
        node_queue = node_stats["queue"]

        queue_msg = (
            _("📦 Cola:\n", locale)
            + _("Total: {total}\n", locale).format(total=total_queue)
            + _("Tu cola: {queue}", locale).format(queue=node_queue)
        )
        return "osmqueue", queue_msg

    def _handle_nodes(self, locale: Optional[str] = None) -> Tuple[str, str]:
        """Handle #osmnodes command - list all known nodes in the mesh."""
        import time
        from datetime import datetime, timedelta
        
        # Get all positions from database
        all_positions = self.db.load_all_positions()
        
        if not all_positions:
            return "osmnodes", _("📡 No hay nodos conocidos en la red\nNo known nodes in the mesh", locale)
        
        # Sort by last seen (most recent first)
        nodes_list = []
        now = time.time()
        
        for node_id, pos_data in all_positions.items():
            received_at = pos_data.get("received_at", 0)
            age_seconds = now - received_at
            
            # Format age
            if age_seconds < 60:
                age_str = _("{sec}s", locale).format(sec=int(age_seconds))
            elif age_seconds < 3600:
                age_str = _("{min}m", locale).format(min=int(age_seconds / 60))
            elif age_seconds < 86400:
                age_str = _("{hr}h", locale).format(hr=int(age_seconds / 3600))
            else:
                age_str = _("{days}d", locale).format(days=int(age_seconds / 86400))
            
            lat = pos_data.get("lat")
            lon = pos_data.get("lon")
            seen_count = pos_data.get("seen_count", 1)
            
            nodes_list.append({
                "node_id": node_id,
                "lat": lat,
                "lon": lon,
                "age": age_seconds,
                "age_str": age_str,
                "seen_count": seen_count,
            })
        
        # Sort by most recent first
        nodes_list.sort(key=lambda x: x["age"])
        
        # Build response message
        header = _("📡 Nodos en la red ({count}):\n", locale).format(count=len(nodes_list))
        nodes_msg = []
        
        for i, node in enumerate(nodes_list[:20], 1):  # Limit to 20 nodes
            node_line = f"{i}. {node['node_id']}"
            if node['lat'] and node['lon']:
                node_line += f" ({node['lat']:.4f}, {node['lon']:.4f})"
            node_line += f" - {_('visto hace', locale)} {node['age_str']}"
            if node['seen_count'] > 1:
                node_line += f" ({node['seen_count']}x)"
            nodes_msg.append(node_line)
        
        if len(nodes_list) > 20:
            nodes_msg.append(_("\n... y {more} más", locale).format(more=len(nodes_list) - 20))
        
        return "osmnodes", header + "\n".join(nodes_msg)

    def _validate_coordinates(self, lat: float, lon: float, locale: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Validate GPS coordinates.

        Args:
            lat: Latitude to validate
            lon: Longitude to validate
            locale: Optional locale for error messages

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for invalid coordinates (0,0 is often a default/error value)
        if lat == 0.0 and lon == 0.0:
            return False, MSG_REJECT_INVALID_COORDS(locale=locale)

        # Check valid ranges
        if not (-90 <= lat <= 90):
            return False, MSG_REJECT_INVALID_COORDS(locale=locale)

        if not (-180 <= lon <= 180):
            return False, MSG_REJECT_INVALID_COORDS(locale=locale)

        return True, None

    def _handle_lang(self, node_id: str, text: str, locale: Optional[str] = None) -> Tuple[str, str]:
        """Handle #osmlang command."""
        parts = text.split()

        # If no language specified, show current language
        if len(parts) == 1:
            current_lang = self.db.get_user_language(node_id)
            lang_display = "Español" if current_lang == "es" else "English"
            return "osmlang", _("🌐 Idioma actual / Current language: {lang}", locale).format(lang=lang_display)

        # Parse language parameter
        if len(parts) >= 2:
            new_lang = parts[1].lower().strip()

            # Validate language
            if new_lang not in ["es", "en"]:
                return "osmlang", _("❌ Idioma inválido. Usa: #osmlang es o #osmlang en\nInvalid language. Use: #osmlang es or #osmlang en", locale)

            # Change language
            try:
                self.db.set_user_language(node_id, new_lang)
                lang_display = "Español" if new_lang == "es" else "English"
                # Use the new language for the response
                return "osmlang", _("✅ Idioma cambiado a {lang} / Language changed to {lang}", new_lang).format(lang=lang_display)
            except Exception as e:
                logger.error(f"Error changing language for {node_id}: {e}")
                return "osmlang", _("❌ Error al cambiar idioma / Error changing language", locale)

        # Fallback
        current_lang = self.db.get_user_language(node_id)
        lang_display = "Español" if current_lang == "es" else "English"
        return "osmlang", _("🌐 Idioma actual / Current language: {lang}", locale).format(lang=lang_display)

    def _handle_osmnote(
        self,
        node_id: str,
        text: str,
        timestamp: Optional[float],
        device_uptime: Optional[float] = None,
        locale: Optional[str] = None,
    ) -> Tuple[str, Optional[str]]:
        """Handle #osmnote command."""
        import time

        # Check message length
        if len(text) > MESHTASTIC_MAX_MESSAGE_LENGTH:
            return "osmnote_reject", MSG_REJECT_MESSAGE_TOO_LONG(
                max_len=MESHTASTIC_MAX_MESSAGE_LENGTH,
                locale=locale
            )

        # Check if text is empty (only hashtag)
        if not text or not text.strip():
            return "osmnote_reject", MSG_FALTA_TEXTO(locale)

        text_normalized = self.normalize_text(text)

        # Get position from cache
        position = self.position_cache.get(node_id)
        logger.debug(f"Position cache lookup for {node_id}: {position}")

        if position:
            logger.debug(f"Position found in cache for {node_id}: lat={position.lat}, lon={position.lon}, age={self.position_cache.get_age(node_id)}s")
        else:
            logger.warning(f"No position found in cache for {node_id}")

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
                        return "osmnote_reject", MSG_REJECT_NO_GPS_RECENT_START(
                            wait_time=wait_time,
                            locale=locale
                        )
                return "osmnote_reject", MSG_REJECT_NO_GPS(locale=locale)

            # Validate coordinates
            is_valid, error_msg = self._validate_coordinates(position.lat, position.lon, locale=locale)
            if not is_valid:
                return "osmnote_reject", error_msg

            # Check position age
            pos_age = self.position_cache.get_age(node_id)
            if pos_age is None or pos_age > POS_MAX:
                # Check if device was recently started
                if device_uptime is not None and device_uptime < DEVICE_UPTIME_RECENT:
                    wait_time = int(DEVICE_UPTIME_GPS_WAIT - device_uptime)
                    if wait_time > 0:
                        return "osmnote_reject", MSG_REJECT_NO_GPS_RECENT_START(
                            wait_time=wait_time,
                            locale=locale
                        )
                return "osmnote_reject", MSG_REJECT_STALE_GPS(locale=locale)

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
            position.lat,
            position.lon,
            time_bucket,
        ):
            return "osmnote_duplicate", MSG_DUPLICATE(locale)

        # Create note
        local_queue_id = self.db.create_note(
            node_id=node_id,
            lat=position.lat,
            lon=position.lon,
            text_original=text,
            text_normalized=text_normalized,
        )

        if not local_queue_id:
            return "osmnote_error", _("❌ Error al crear nota.", locale)

        # Return queued status with queue_id for extraction
        return "osmnote_queued", local_queue_id
