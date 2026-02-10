"""OSM Notes API worker."""

import time
import logging
import requests
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from collections import defaultdict

from .config import (
    OSM_API_URL, OSM_RATE_LIMIT_SECONDS, DRY_RUN,
    OSM_MAX_RETRIES, OSM_RETRY_DELAY_SECONDS,
)
from .database import Database
from .i18n import _

logger = logging.getLogger(__name__)


class OSMWorker:
    """Worker for sending notes to OSM API."""

    def __init__(self, db: Database):
        self.db = db
        self.last_send_time = 0.0
        self.retry_counts: Dict[str, int] = {}  # Track retry counts per queue_id
        self._last_error_detail: Optional[str] = None  # Store last error detail for process_pending

    def send_note(
        self,
        lat: float,
        lon: float,
        text: str,
        locale: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Send note to OSM Notes API with rate limiting.
        
        Implements rate limiting (minimum 3 seconds between sends) and
        handles various error conditions gracefully.
        
        Args:
            lat: Latitude coordinate
            lon: Longitude coordinate
            text: Note text content (should be normalized)
            
        Returns:
            Dictionary with 'id' and 'url' keys on success, None on failure.
            In DRY_RUN mode, returns mock data.
            
        Raises:
            No exceptions raised - all errors are logged and None is returned.
            
        Examples:
            >>> result = worker.send_note(4.6097, -74.0817, "Test note")
            >>> result
            {'id': 12345, 'url': 'https://www.openstreetmap.org/note/12345'}
        """
        if DRY_RUN:
            logger.info(f"[DRY_RUN] Would send note: ({lat}, {lon}) - {text[:50]}...")
            # Return mock data for testing
            return {
                "id": 999999,
                "url": "https://www.openstreetmap.org/note/999999",
            }

        # Rate limiting
        now = time.time()
        time_since_last = now - self.last_send_time
        if time_since_last < OSM_RATE_LIMIT_SECONDS:
            sleep_time = OSM_RATE_LIMIT_SECONDS - time_since_last
            logger.debug(f"Rate limiting: sleeping {sleep_time:.1f}s")
            time.sleep(sleep_time)

        try:
            # Add project attribution to note text (translated to user's language)
            if locale is None:
                locale = "es"  # Default to Spanish
            attribution = _("\n\n---\nCreado mediante OSM Mesh Notes Gateway (LoRa mesh → OSM Notes)", locale)
            note_text = text + attribution
            
            # Prepare request
            payload = {
                "lat": lat,
                "lon": lon,
                "text": note_text,
            }

            logger.info(f"Sending note to OSM: ({lat}, {lon}) - {text[:50]}...")

            response = requests.post(
                OSM_API_URL,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"},
            )

            self.last_send_time = time.time()

            if response.status_code == 200:
                data = response.json()
                note_id = data.get("properties", {}).get("id")
                note_url = f"https://www.openstreetmap.org/note/{note_id}"

                logger.info(f"Note created successfully: #{note_id} - {note_url}")
                return {
                    "id": note_id,
                    "url": note_url,
                }
            else:
                # Parse error response
                error_detail = self._parse_osm_error(response.status_code, response.text)
                error_msg = f"OSM API error {response.status_code}: {error_detail}"
                logger.error(error_msg)
                # Store error detail for later retrieval
                self._last_error_detail = error_detail
                return None

        except requests.exceptions.Timeout:
            error_msg = "OSM API timeout"
            logger.error(error_msg)
            self._last_error_detail = "Timeout al conectar con OSM API"
            return None
        except requests.exceptions.ConnectionError:
            error_msg = "OSM API connection error (no internet?)"
            logger.error(error_msg)
            self._last_error_detail = "Error de conexión (sin Internet?)"
            return None
        except Exception as e:
            error_msg = f"Unexpected error sending to OSM: {e}"
            logger.error(error_msg)
            self._last_error_detail = f"Error inesperado: {str(e)[:50]}"
            return None

    def _parse_osm_error(self, status_code: int, response_text: str) -> str:
        """
        Parse OSM API error response and return user-friendly message.
        
        Returns:
            Human-readable error message
        """
        # Common OSM API errors
        if status_code == 400:
            return "Solicitud inválida (coordenadas o texto incorrectos)"
        elif status_code == 403:
            return "Acceso denegado (posible rate limiting)"
        elif status_code == 429:
            return "Demasiadas solicitudes (rate limiting)"
        elif status_code == 500:
            return "Error del servidor OSM"
        elif status_code == 503:
            return "Servicio OSM temporalmente no disponible"
        else:
            # Try to extract error message from response
            try:
                import json
                data = json.loads(response_text)
                error_msg = data.get("error", {}).get("message") or data.get("message", "")
                if error_msg:
                    return error_msg[:100]
            except:
                pass
            return response_text[:100] if response_text else "Error desconocido"

    def process_pending(self, limit: int = 10) -> int:
        """
        Process pending notes.
        Returns: number of notes successfully sent.
        """
        pending = self.db.get_pending_notes(limit=limit)
        if not pending:
            return 0

        sent_count = 0
        for note in pending:
            queue_id = note["local_queue_id"]
            
            # Get retry count
            retry_count = self.retry_counts.get(queue_id, 0)
            
            # Check if max retries exceeded
            if retry_count >= OSM_MAX_RETRIES:
                error_msg = f"Falló después de {OSM_MAX_RETRIES} intentos. Revisa logs."
                self.db.update_note_error(queue_id, error_msg, retry_count=retry_count)
                logger.warning(f"Max retries exceeded for {queue_id}")
                # Remove from retry tracking
                del self.retry_counts[queue_id]
                continue
            
            # Get user's preferred language for attribution
            user_locale = self.db.get_user_language(note["node_id"])
            
            result = self.send_note(
                lat=note["lat"],
                lon=note["lon"],
                text=note["text_normalized"],
                locale=user_locale,
            )

            if result:
                # Success - update note and clear retry count
                self.db.update_note_sent(
                    local_queue_id=queue_id,
                    osm_note_id=result["id"],
                    osm_note_url=result["url"],
                )
                if queue_id in self.retry_counts:
                    del self.retry_counts[queue_id]
                sent_count += 1
            else:
                # Failure - increment retry count
                retry_count += 1
                self.retry_counts[queue_id] = retry_count
                
                # Get error message - use last error detail from send_note if available
                if self._last_error_detail:
                    last_error = self._last_error_detail
                    self._last_error_detail = None  # Clear after use
                else:
                    # Get last error from note if available, otherwise use default
                    note_data = self.db.get_note_by_queue_id(queue_id)
                    if note_data and note_data.get("last_error"):
                        last_error = note_data.get("last_error")
                    else:
                        # Default error message if not set yet
                        last_error = "Error al enviar a OSM API"
                
                # Update with error and retry count
                self.db.update_note_error(
                    local_queue_id=queue_id,
                    error=last_error,
                    retry_count=retry_count,
                )
                
                # If not max retries, note will be retried later
                if retry_count < OSM_MAX_RETRIES:
                    logger.info(f"Will retry {queue_id} later (attempt {retry_count}/{OSM_MAX_RETRIES})")
                    # Sleep before next retry
                    time.sleep(OSM_RETRY_DELAY_SECONDS)

        return sent_count
