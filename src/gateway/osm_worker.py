"""OSM Notes API worker."""

import time
import logging
import requests
from typing import Optional, Dict, Any
from datetime import datetime

from .config import OSM_API_URL, OSM_RATE_LIMIT_SECONDS, DRY_RUN
from .database import Database

logger = logging.getLogger(__name__)


class OSMWorker:
    """Worker for sending notes to OSM API."""

    def __init__(self, db: Database):
        self.db = db
        self.last_send_time = 0.0

    def send_note(
        self,
        lat: float,
        lon: float,
        text: str,
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
            # Prepare request
            payload = {
                "lat": lat,
                "lon": lon,
                "text": text,
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
                error_msg = f"OSM API error {response.status_code}: {response.text[:200]}"
                logger.error(error_msg)
                return None

        except requests.exceptions.Timeout:
            error_msg = "OSM API timeout"
            logger.error(error_msg)
            return None
        except requests.exceptions.ConnectionError:
            error_msg = "OSM API connection error (no internet?)"
            logger.error(error_msg)
            return None
        except Exception as e:
            error_msg = f"Unexpected error sending to OSM: {e}"
            logger.error(error_msg)
            return None

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
            result = self.send_note(
                lat=note["lat"],
                lon=note["lon"],
                text=note["text_normalized"],
            )

            if result:
                # Update note as sent
                self.db.update_note_sent(
                    local_queue_id=note["local_queue_id"],
                    osm_note_id=result["id"],
                    osm_note_url=result["url"],
                )
                sent_count += 1
            else:
                # Update with error
                error_msg = "Failed to send to OSM API"
                self.db.update_note_error(
                    local_queue_id=note["local_queue_id"],
                    error=error_msg,
                )

        return sent_count
