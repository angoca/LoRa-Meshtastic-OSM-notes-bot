"""Tests for edge cases in database operations."""

import pytest
import time
from gateway.database import Database


@pytest.fixture
def db(tmp_path):
    """Create temporary database."""
    db_path = tmp_path / "test.db"
    return Database(db_path=db_path)


def test_get_note_by_queue_id_not_found(db):
    """Test getting non-existent note."""
    note = db.get_note_by_queue_id("Q-9999")
    assert note is None


def test_get_node_stats_empty(db):
    """Test getting stats for node with no notes."""
    stats = db.get_node_stats("nonexistent")
    assert stats["total"] == 0
    assert stats["today"] == 0
    assert stats["queue"] == 0


def test_get_node_notes_empty(db):
    """Test getting notes for node with no notes."""
    notes = db.get_node_notes("nonexistent")
    assert len(notes) == 0


def test_get_node_notes_with_limit(db):
    """Test getting notes with limit."""
    node_id = "test_node"
    
    # Create 10 notes
    for i in range(10):
        db.create_note(node_id, 1.0, 2.0, f"test{i}", f"test{i}")
    
    # Get with limit
    notes = db.get_node_notes(node_id, limit=5)
    assert len(notes) == 5


def test_get_node_notes_exclude_pending(db):
    """Test getting notes excluding pending."""
    node_id = "test_node"
    
    # Create notes
    queue_id1 = db.create_note(node_id, 1.0, 2.0, "test1", "test1")
    queue_id2 = db.create_note(node_id, 1.0, 2.0, "test2", "test2")
    
    # Mark one as sent
    db.update_note_sent(queue_id1, 12345, "https://osm.org/note/12345")
    
    # Get notes excluding pending
    notes = db.get_node_notes(node_id, limit=10, include_pending=False)
    assert len(notes) == 1
    assert notes[0]["status"] == "sent"


def test_get_total_queue_size_empty(db):
    """Test getting queue size when empty."""
    size = db.get_total_queue_size()
    assert size == 0


def test_get_total_queue_size(db):
    """Test getting queue size."""
    # Create pending notes
    db.create_note("node1", 1.0, 2.0, "test1", "test1")
    db.create_note("node2", 1.0, 2.0, "test2", "test2")
    
    size = db.get_total_queue_size()
    assert size == 2


def test_get_pending_for_notification(db):
    """Test getting pending notifications."""
    # Create sent note
    queue_id = db.create_note("node1", 1.0, 2.0, "test", "test")
    db.update_note_sent(queue_id, 12345, "https://osm.org/note/12345")
    
    pending = db.get_pending_for_notification()
    assert len(pending) == 1
    assert pending[0]["local_queue_id"] == queue_id
    assert pending[0]["notified_sent"] == 0


def test_mark_notified_sent(db):
    """Test marking note as notified."""
    queue_id = db.create_note("node1", 1.0, 2.0, "test", "test")
    db.update_note_sent(queue_id, 12345, "https://osm.org/note/12345")
    
    db.mark_notified_sent(queue_id)
    
    note = db.get_note_by_queue_id(queue_id)
    assert note["notified_sent"] == 1


def test_update_note_error(db):
    """Test updating note with error."""
    queue_id = db.create_note("node1", 1.0, 2.0, "test", "test")
    
    db.update_note_error(queue_id, "Test error message")
    
    note = db.get_note_by_queue_id(queue_id)
    assert note["last_error"] == "Test error message"


def test_check_duplicate_different_time_bucket(db):
    """Test duplicate check with different time buckets."""
    node_id = "test_node"
    text = "test message"
    lat, lon = 1.0, 2.0
    
    # Create first note - will be in current time bucket
    import time
    import gateway.config
    current_time = time.time()
    current_bucket = int(current_time / gateway.config.DEDUP_TIME_BUCKET_SECONDS)
    
    db.create_note(node_id, lat, lon, text, text)
    
    # Check duplicate in same bucket
    is_dup1 = db.check_duplicate(node_id, text, lat, lon, current_bucket)
    assert is_dup1, "Should be duplicate in same bucket"
    
    # Check duplicate in different bucket (should not be duplicate)
    # Use a bucket far in the future
    future_bucket = current_bucket + 1000
    is_dup2 = db.check_duplicate(node_id, text, lat, lon, future_bucket)
    assert not is_dup2, "Should NOT be duplicate in different bucket"
