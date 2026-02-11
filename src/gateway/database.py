"""SQLite database management."""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import pytz

from .config import DB_PATH, DEDUP_LOCATION_PRECISION, DEDUP_TIME_BUCKET_SECONDS, OSM_MAX_RETRIES, TZ

logger = logging.getLogger(__name__)


class Database:
    """Database manager for notes storage."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            # Configure SQLite for power loss tolerance
            # WAL mode provides better concurrency and crash recovery
            conn.execute("PRAGMA journal_mode=WAL")
            # Full sync for data integrity (slower but safer for power loss)
            conn.execute("PRAGMA synchronous=FULL")
            # Checkpoint WAL periodically to prevent it from growing too large
            conn.execute("PRAGMA wal_autocheckpoint=1000")
            
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
                CREATE TABLE IF NOT EXISTS position_cache (
                    node_id TEXT PRIMARY KEY,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    received_at REAL NOT NULL,
                    seen_count INTEGER DEFAULT 1,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    node_id TEXT PRIMARY KEY,
                    language TEXT DEFAULT 'es',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        """
        Get database connection with proper error handling and power loss tolerance.
        
        Configures SQLite with:
        - WAL mode for better concurrency and crash recovery
        - FULL synchronous mode for data integrity during power loss
        - Proper timeout for busy database handling
        """
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        
        # Configure for power loss tolerance (if not already set)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
        except sqlite3.Error:
            pass  # May fail if database is locked, that's OK
        
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

    def update_note_error(self, local_queue_id: str, error: str, retry_count: Optional[int] = None):
        """Update note with error message and optionally retry count."""
        with self._get_connection() as conn:
            if retry_count is not None:
                # Store retry count in error message for now (could add retry_count column later)
                error_with_retry = f"{error} (intento {retry_count}/{OSM_MAX_RETRIES})"
            else:
                error_with_retry = error
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

    def get_node_stats(self, node_id: str, timezone: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for a node.
        
        Args:
            node_id: Node identifier
            timezone: Timezone name (e.g., 'America/Bogota'). If None, uses TZ from config.
        
        Returns:
            Dictionary with 'total', 'today', 'queue', and 'timezone' keys.
        """
        if timezone is None:
            timezone = TZ
        
        with self._get_connection() as conn:
            # Total count
            cursor = conn.execute("""
                SELECT COUNT(*) as total FROM notes WHERE node_id = ?
            """, (node_id,))
            total = cursor.fetchone()["total"]

            # Today count (using server timezone)
            # Notes are stored in UTC, so we need to convert to server timezone
            tz = pytz.timezone(timezone)
            now_local = datetime.now(tz)
            today_local = now_local.strftime("%Y-%m-%d")
            
            # Get all notes for this node and filter by date in server timezone
            cursor = conn.execute("""
                SELECT created_at FROM notes WHERE node_id = ?
            """, (node_id,))
            notes = cursor.fetchall()
            
            today_count = 0
            for note_row in notes:
                # Parse UTC datetime from database
                # SQLite stores datetime as string, format: 'YYYY-MM-DD HH:MM:SS.ffffff'
                created_str = note_row["created_at"]
                try:
                    # Try parsing with timezone info first
                    if 'Z' in created_str or '+' in created_str or created_str.endswith('UTC'):
                        created_utc = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                    else:
                        # No timezone info, assume UTC (as stored by datetime.utcnow())
                        created_utc = datetime.fromisoformat(created_str)
                        created_utc = pytz.UTC.localize(created_utc)
                    
                    # Convert to server timezone
                    created_local = created_utc.astimezone(tz)
                    if created_local.strftime("%Y-%m-%d") == today_local:
                        today_count += 1
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Error parsing date {created_str}: {e}")
                    continue

            # Queue size
            cursor = conn.execute("""
                SELECT COUNT(*) as queue FROM notes
                WHERE node_id = ? AND status = 'pending'
            """, (node_id,))
            queue = cursor.fetchone()["queue"]

            return {
                "total": total,
                "today": today_count,
                "queue": queue,
                "timezone": timezone,
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

    def get_failed_notes_for_notification(self) -> List[Dict[str, Any]]:
        """Get notes that failed after max retries and need error notification."""
        with self._get_connection() as conn:
            # Get notes with errors that mention max retries
            cursor = conn.execute("""
                SELECT * FROM notes
                WHERE status = 'pending' 
                  AND last_error IS NOT NULL
                  AND last_error LIKE '%intento%/%'
                  AND notified_sent = 0
                ORDER BY created_at ASC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def save_position(self, node_id: str, lat: float, lon: float, received_at: float, seen_count: int = 1):
        """Save or update position in persistent cache."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO position_cache (node_id, lat, lon, received_at, seen_count, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(node_id) DO UPDATE SET
                    lat = excluded.lat,
                    lon = excluded.lon,
                    received_at = excluded.received_at,
                    seen_count = seen_count + 1,
                    updated_at = CURRENT_TIMESTAMP
            """, (node_id, lat, lon, received_at, seen_count))
            conn.commit()

    def get_position(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get position from persistent cache."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT node_id, lat, lon, received_at, seen_count
                FROM position_cache
                WHERE node_id = ?
            """, (node_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def load_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """Load all positions from persistent cache."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT node_id, lat, lon, received_at, seen_count
                FROM position_cache
            """)
            return {row["node_id"]: dict(row) for row in cursor.fetchall()}

    def cleanup_old_positions(self, max_age_seconds: float = 86400):
        """Remove positions older than max_age_seconds (default: 24 hours)."""
        import time
        cutoff_time = time.time() - max_age_seconds
        with self._get_connection() as conn:
            conn.execute("""
                DELETE FROM position_cache
                WHERE received_at < ?
            """, (cutoff_time,))
            conn.commit()
            deleted = conn.total_changes
            if deleted > 0:
                logger.debug(f"Cleaned up {deleted} old positions from cache")

    def get_user_language(self, node_id: str) -> str:
        """Get user's preferred language (default: 'es')."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT language FROM user_preferences
                WHERE node_id = ?
            """, (node_id,))
            row = cursor.fetchone()
            return row["language"] if row else "es"

    def set_user_language(self, node_id: str, language: str) -> bool:
        """Set user's preferred language. Returns True if successful."""
        if language not in ["es", "en"]:
            return False
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO user_preferences (node_id, language, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(node_id) DO UPDATE SET
                    language = excluded.language,
                    updated_at = CURRENT_TIMESTAMP
            """, (node_id, language))
            conn.commit()
            return True

    def get_last_broadcast_date(self) -> Optional[str]:
        """Get the date of the last broadcast (YYYY-MM-DD format)."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT value FROM system_state
                WHERE key = 'last_broadcast_date'
            """)
            row = cursor.fetchone()
            return row["value"] if row else None

    def set_last_broadcast_date(self, date: str):
        """Set the date of the last broadcast (YYYY-MM-DD format)."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO system_state (key, value, updated_at)
                VALUES ('last_broadcast_date', ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
            """, (date,))
            conn.commit()

    def get_startup_timestamp(self) -> Optional[float]:
        """Get the startup timestamp (Unix timestamp) when the service started."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT value FROM system_state
                WHERE key = 'startup_timestamp'
            """)
            row = cursor.fetchone()
            return float(row["value"]) if row else None

    def set_startup_timestamp(self, timestamp: float):
        """Set the startup timestamp (Unix timestamp)."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO system_state (key, value, updated_at)
                VALUES ('startup_timestamp', ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
            """, (str(timestamp),))
            conn.commit()

    def get_time_correction_applied(self) -> bool:
        """Check if time correction has already been applied."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT value FROM system_state
                WHERE key = 'time_correction_applied'
            """)
            row = cursor.fetchone()
            return row and row["value"] == "true"

    def set_time_correction_applied(self, applied: bool = True):
        """Mark that time correction has been applied."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO system_state (key, value, updated_at)
                VALUES ('time_correction_applied', ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
            """, ("true" if applied else "false",))
            conn.commit()

    def adjust_pending_notes_timestamps(self, time_offset_seconds: float) -> int:
        """
        Adjust timestamps of pending notes by adding time_offset_seconds.
        
        Only adjusts notes with status='pending' that were created before the correction.
        Does not modify notes with status='sent' (already sent to OSM).
        
        Args:
            time_offset_seconds: Number of seconds to add to timestamps (can be negative)
            
        Returns:
            Number of notes adjusted
        """
        if abs(time_offset_seconds) < 1.0:
            # Ignore very small offsets (< 1 second)
            return 0
            
        with self._get_connection() as conn:
            # Update created_at for pending notes
            # SQLite datetime arithmetic: add seconds using datetime(created_at, '+X seconds')
            cursor = conn.execute("""
                UPDATE notes
                SET created_at = datetime(created_at, ? || ' seconds')
                WHERE status = 'pending'
            """, (time_offset_seconds,))
            conn.commit()
            adjusted_count = cursor.rowcount
            
            if adjusted_count > 0:
                logger.info(f"Adjusted timestamps of {adjusted_count} pending notes by {time_offset_seconds:.1f} seconds")
            
            return adjusted_count
