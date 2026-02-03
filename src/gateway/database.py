"""SQLite database management."""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from .config import DB_PATH, DEDUP_LOCATION_PRECISION, DEDUP_TIME_BUCKET_SECONDS

logger = logging.getLogger(__name__)


class Database:
    """Database manager for notes storage."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    local_queue_id TEXT UNIQUE NOT NULL,
                    node_id TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    text_original TEXT NOT NULL,
                    text_normalized TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    osm_note_id INTEGER,
                    osm_note_url TEXT,
                    sent_at TIMESTAMP,
                    last_error TEXT,
                    notified_sent INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_notes_node_id ON notes(node_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_notes_status ON notes(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_notes_created_at ON notes(created_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_notes_node_created ON notes(node_id, created_at)
            """)
            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """Get database connection with proper error handling."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_note(
        self,
        node_id: str,
        lat: float,
        lon: float,
        text_original: str,
        text_normalized: str,
    ) -> Optional[str]:
        """
        Create a new note in the database.
        
        Args:
            node_id: Meshtastic node ID that created the note
            lat: Latitude coordinate
            lon: Longitude coordinate
            text_original: Original message text
            text_normalized: Normalized text for deduplication
            
        Returns:
            local_queue_id (e.g., "Q-0001") if successful, None on error
            
        Note:
            Automatically generates sequential queue IDs. If collision occurs,
            retries with higher number.
        """
        # Generate local_queue_id
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM notes")
            count = cursor.fetchone()["count"]
            local_queue_id = f"Q-{count + 1:04d}"

            try:
                conn.execute("""
                    INSERT INTO notes (
                        local_queue_id, node_id, created_at, lat, lon,
                        text_original, text_normalized, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
                """, (
                    local_queue_id,
                    node_id,
                    datetime.utcnow(),
                    lat,
                    lon,
                    text_original,
                    text_normalized,
                ))
                conn.commit()
                logger.info(f"Created note {local_queue_id} for node {node_id}")
                return local_queue_id
            except sqlite3.IntegrityError:
                logger.warning(f"Duplicate local_queue_id {local_queue_id}, retrying...")
                # Retry with higher number
                cursor = conn.execute("SELECT COUNT(*) as count FROM notes")
                count = cursor.fetchone()["count"]
                local_queue_id = f"Q-{count + 100:04d}"
                conn.execute("""
                    INSERT INTO notes (
                        local_queue_id, node_id, created_at, lat, lon,
                        text_original, text_normalized, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
                """, (
                    local_queue_id,
                    node_id,
                    datetime.utcnow(),
                    lat,
                    lon,
                    text_original,
                    text_normalized,
                ))
                conn.commit()
                return local_queue_id

    def get_pending_notes(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get pending notes ordered by created_at."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM notes
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_note_by_queue_id(self, local_queue_id: str) -> Optional[Dict[str, Any]]:
        """Get a note by its local_queue_id."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM notes
                WHERE local_queue_id = ?
            """, (local_queue_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_note_sent(
        self,
        local_queue_id: str,
        osm_note_id: int,
        osm_note_url: str,
    ):
        """Mark note as sent with OSM details."""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE notes
                SET status = 'sent',
                    osm_note_id = ?,
                    osm_note_url = ?,
                    sent_at = ?
                WHERE local_queue_id = ?
            """, (osm_note_id, osm_note_url, datetime.utcnow(), local_queue_id))
            conn.commit()
            logger.info(f"Marked note {local_queue_id} as sent (OSM #{osm_note_id})")

    def update_note_error(self, local_queue_id: str, error: str):
        """Update note with error message."""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE notes
                SET last_error = ?
                WHERE local_queue_id = ?
            """, (error, local_queue_id))
            conn.commit()

    def mark_notified_sent(self, local_queue_id: str):
        """Mark note as notified (sent notification sent)."""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE notes
                SET notified_sent = 1
                WHERE local_queue_id = ?
            """, (local_queue_id,))
            conn.commit()

    def get_node_stats(self, node_id: str) -> Dict[str, Any]:
        """Get statistics for a node."""
        with self._get_connection() as conn:
            # Total count
            cursor = conn.execute("""
                SELECT COUNT(*) as total FROM notes WHERE node_id = ?
            """, (node_id,))
            total = cursor.fetchone()["total"]

            # Today count
            cursor = conn.execute("""
                SELECT COUNT(*) as today FROM notes
                WHERE node_id = ? AND DATE(created_at) = DATE('now')
            """, (node_id,))
            today = cursor.fetchone()["today"]

            # Queue size
            cursor = conn.execute("""
                SELECT COUNT(*) as queue FROM notes
                WHERE node_id = ? AND status = 'pending'
            """, (node_id,))
            queue = cursor.fetchone()["queue"]

            return {
                "total": total,
                "today": today,
                "queue": queue,
            }

    def get_node_notes(
        self,
        node_id: str,
        limit: int = 5,
        include_pending: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get recent notes for a node."""
        with self._get_connection() as conn:
            if include_pending:
                cursor = conn.execute("""
                    SELECT * FROM notes
                    WHERE node_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (node_id, limit))
            else:
                cursor = conn.execute("""
                    SELECT * FROM notes
                    WHERE node_id = ? AND status = 'sent'
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (node_id, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_total_queue_size(self) -> int:
        """Get total pending queue size."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM notes WHERE status = 'pending'")
            return cursor.fetchone()["count"]

    def check_duplicate(
        self,
        node_id: str,
        text_normalized: str,
        lat: float,
        lon: float,
        time_bucket: int,
    ) -> bool:
        """Check if a note is a duplicate based on deduplication rules."""
        # Round coordinates
        lat_rounded = round(lat, DEDUP_LOCATION_PRECISION)
        lon_rounded = round(lon, DEDUP_LOCATION_PRECISION)

        with self._get_connection() as conn:
            # Check for duplicates in the same time bucket
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM notes
                WHERE node_id = ?
                  AND text_normalized = ?
                  AND ABS(lat - ?) < 0.0001
                  AND ABS(lon - ?) < 0.0001
                  AND CAST(strftime('%s', created_at) / ? AS INTEGER) = ?
            """, (
                node_id,
                text_normalized,
                lat_rounded,
                lon_rounded,
                DEDUP_TIME_BUCKET_SECONDS,
                time_bucket,
            ))
            count = cursor.fetchone()["count"]
            return count > 0

    def get_pending_for_notification(self) -> List[Dict[str, Any]]:
        """Get pending notes that need sent notification."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM notes
                WHERE status = 'sent' AND notified_sent = 0
                ORDER BY sent_at ASC
            """)
            return [dict(row) for row in cursor.fetchall()]
