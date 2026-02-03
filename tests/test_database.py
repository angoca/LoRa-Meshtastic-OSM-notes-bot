"""Tests for database operations."""

import pytest
import time
from gateway.database import Database


@pytest.fixture
def db(tmp_path):
    """Create temporary database."""
    db_path = tmp_path / "test.db"
    return Database(db_path=db_path)


def test_create_note(db):
    """Test note creation."""
    queue_id = db.create_note(
        node_id="test_node",
        lat=1.0,
        lon=2.0,
        text_original="test",
        text_normalized="test",
    )
    assert queue_id.startswith("Q-")
    assert queue_id == "Q-0001"


def test_get_pending_notes(db):
    """Test getting pending notes."""
    # Create notes
    db.create_note("node1", 1.0, 2.0, "test1", "test1")
    db.create_note("node2", 3.0, 4.0, "test2", "test2")
    
    pending = db.get_pending_notes()
    assert len(pending) == 2


def test_update_note_sent(db):
    """Test marking note as sent."""
    queue_id = db.create_note("node1", 1.0, 2.0, "test", "test")
    
    db.update_note_sent(queue_id, 12345, "https://osm.org/note/12345")
    
    pending = db.get_pending_notes()
    assert len(pending) == 0


def test_get_node_stats(db):
    """Test node statistics."""
    node_id = "test_node"
    
    # Create notes
    db.create_note(node_id, 1.0, 2.0, "test1", "test1")
    db.create_note(node_id, 1.0, 2.0, "test2", "test2")
    
    stats = db.get_node_stats(node_id)
    assert stats["total"] == 2
    assert stats["queue"] == 2


def test_check_duplicate(db):
    """Test duplicate detection."""
    node_id = "test_node"
    text = "test message"
    lat, lon = 1.0, 2.0
    time_bucket = int(time.time() / 120)
    
    # Create note
    db.create_note(node_id, lat, lon, text, text)
    
    # Check duplicate
    is_dup = db.check_duplicate(node_id, text, lat, lon, time_bucket)
    assert is_dup
    
    # Different text
    is_dup2 = db.check_duplicate(node_id, "different", lat, lon, time_bucket)
    assert not is_dup2
    
    # Different location
    is_dup3 = db.check_duplicate(node_id, text, 10.0, 20.0, time_bucket)
    assert not is_dup3
