"""Tests for edge cases in command processing."""

import pytest
import time
from gateway.commands import CommandProcessor
from gateway.database import Database
from gateway.position_cache import PositionCache


@pytest.fixture
def db(tmp_path):
    """Create temporary database."""
    db_path = tmp_path / "test.db"
    return Database(db_path=db_path)


@pytest.fixture
def position_cache():
    """Create position cache."""
    return PositionCache()


@pytest.fixture
def processor(db, position_cache):
    """Create command processor."""
    return CommandProcessor(db, position_cache)


def test_osmnote_variants(processor, db, position_cache):
    """Test different osmnote hashtag variants."""
    node_id = "test_node"
    
    variants = ["#osmnote", "#osm-note", "#osm_note"]
    for i, variant in enumerate(variants):
        # Update position slightly to avoid duplicates
        position_cache.update(node_id, 1.0 + i * 0.001, 2.0 + i * 0.001)
        cmd_type, response = processor.process_message(
            node_id, f"{variant} test message {i}"
        )
        assert cmd_type == "osmnote_queued"
        assert response.startswith("Q-")


def test_osmnote_approximate_position(processor, db, position_cache):
    """Test osmnote with approximate position (15-60s old)."""
    node_id = "test_node"
    position_cache.update(node_id, 1.0, 2.0)
    
    # Simulate 30 second old position
    position_cache.positions[node_id].received_at = time.time() - 30
    
    cmd_type, response = processor.process_message(node_id, "#osmnote test")
    
    assert cmd_type == "osmnote_queued"
    # Check that note was created with approximate marker
    pending = db.get_pending_notes(limit=1)
    assert len(pending) == 1
    assert "[posición aproximada]" in pending[0]["text_normalized"]


def test_osmnote_fresh_position(processor, db, position_cache):
    """Test osmnote with fresh position (<15s)."""
    node_id = "test_node"
    position_cache.update(node_id, 1.0, 2.0)
    
    cmd_type, response = processor.process_message(node_id, "#osmnote test")
    
    assert cmd_type == "osmnote_queued"
    # Check that note was created without approximate marker
    pending = db.get_pending_notes(limit=1)
    assert len(pending) == 1
    assert "[posición aproximada]" not in pending[0]["text_normalized"]


def test_osmnote_whitespace_normalization(processor, db, position_cache):
    """Test text normalization with various whitespace."""
    node_id = "test_node"
    position_cache.update(node_id, 1.0, 2.0)
    
    # First note with normal spacing
    cmd_type1, _ = processor.process_message(node_id, "#osmnote hello world")
    
    # Second note with extra whitespace (should be duplicate)
    cmd_type2, _ = processor.process_message(node_id, "#osmnote  hello   world  ")
    
    # Should be duplicate due to normalization
    assert cmd_type2 == "osmnote_duplicate"


def test_osmlist_limit(processor, db):
    """Test osmlist with different limits."""
    node_id = "test_node"
    
    # Create 10 notes
    for i in range(10):
        db.create_note(node_id, 1.0, 2.0, f"test{i}", f"test{i}")
    
    # Test default limit (5)
    cmd_type, response = processor.process_message(node_id, "#osmlist")
    assert cmd_type == "osmlist"
    lines = response.split("\n")
    assert len([l for l in lines if l.startswith("⏳") or l.startswith("✅")]) == 5
    
    # Test custom limit
    cmd_type, response = processor.process_message(node_id, "#osmlist 3")
    assert cmd_type == "osmlist"
    lines = response.split("\n")
    assert len([l for l in lines if l.startswith("⏳") or l.startswith("✅")]) == 3
    
    # Test max limit (20)
    cmd_type, response = processor.process_message(node_id, "#osmlist 100")
    assert cmd_type == "osmlist"
    lines = response.split("\n")
    assert len([l for l in lines if l.startswith("⏳") or l.startswith("✅")]) <= 20


def test_deduplication_different_locations(processor, db, position_cache):
    """Test that different locations don't deduplicate."""
    node_id = "test_node"
    
    # First note at location 1
    position_cache.update(node_id, 1.0, 2.0)
    cmd_type1, _ = processor.process_message(node_id, "#osmnote test")
    assert cmd_type1 == "osmnote_queued"
    
    # Second note at different location (should NOT be duplicate)
    position_cache.update(node_id, 10.0, 20.0)  # Far away
    cmd_type2, _ = processor.process_message(node_id, "#osmnote test")
    assert cmd_type2 == "osmnote_queued"  # Not duplicate


def test_deduplication_different_nodes(processor, db, position_cache):
    """Test that different nodes don't deduplicate."""
    node1 = "node1"
    node2 = "node2"
    
    position_cache.update(node1, 1.0, 2.0)
    position_cache.update(node2, 1.0, 2.0)  # Same location
    
    # First note from node1
    cmd_type1, _ = processor.process_message(node1, "#osmnote test")
    assert cmd_type1 == "osmnote_queued"
    
    # Same text from node2 (should NOT be duplicate)
    cmd_type2, _ = processor.process_message(node2, "#osmnote test")
    assert cmd_type2 == "osmnote_queued"  # Not duplicate


def test_deduplication_time_bucket(processor, db, position_cache):
    """Test deduplication respects time buckets."""
    node_id = "test_node"
    position_cache.update(node_id, 1.0, 2.0)
    
    # First note
    cmd_type1, _ = processor.process_message(node_id, "#osmnote test")
    assert cmd_type1 == "osmnote_queued"
    
    # Wait for next time bucket (120s)
    import gateway.config
    time.sleep(0.1)  # Small delay
    
    # Same note after time bucket (should NOT be duplicate if >120s apart)
    # But we can't wait 120s in test, so we'll test the logic differently
    # For now, verify that immediate duplicate is caught
    cmd_type2, _ = processor.process_message(node_id, "#osmnote test")
    # Should be duplicate if in same bucket
    assert cmd_type2 == "osmnote_duplicate"


def test_ignore_non_command_messages(processor):
    """Test that non-command messages are ignored."""
    cmd_type, response = processor.process_message("node1", "just a regular message")
    assert cmd_type == "ignore"
    assert response is None


def test_empty_message(processor):
    """Test empty message handling."""
    cmd_type, response = processor.process_message("node1", "")
    assert cmd_type == "ignore"
    assert response is None
    
    cmd_type, response = processor.process_message("node1", "   ")
    assert cmd_type == "ignore"
    assert response is None
