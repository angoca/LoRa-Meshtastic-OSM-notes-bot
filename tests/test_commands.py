"""Tests for command processing."""

import pytest
import time
from unittest.mock import Mock, MagicMock

from gateway.commands import CommandProcessor
from gateway.database import Database
from gateway.position_cache import PositionCache


@pytest.fixture
def db(tmp_path):
    """Create temporary database."""
    db_path = tmp_path / "test.db"
    return Database(db_path=db_path)


@pytest.fixture
def position_cache(db):
    """Create position cache with database."""
    return PositionCache(db=db)


@pytest.fixture
def processor(db, position_cache):
    """Create command processor."""
    return CommandProcessor(db, position_cache)


def test_normalize_text(processor):
    """Test text normalization."""
    assert processor.normalize_text("  hello   world  ") == "hello world"
    assert processor.normalize_text("hello\n\nworld") == "hello world"
    assert processor.normalize_text("  test  ") == "test"


def test_extract_osmnote(processor):
    """Test osmnote extraction."""
    assert processor.extract_osmnote("#osmnote hello") == "hello"
    assert processor.extract_osmnote("#osm-note test") == "test"
    assert processor.extract_osmnote("#osm_note message") == "message"
    assert processor.extract_osmnote("#osmnote") == ""
    assert processor.extract_osmnote("no hashtag") is None


def test_extract_osmnote_word_boundary_bug(processor):
    """Test that #osmnotetest (without space) does NOT match #osmnote."""
    # This tests the bug fix: substring check vs regex word boundaries mismatch
    # Before fix: would return "#osmnotetest" (incorrect)
    # After fix: returns None (correct - not a valid #osmnote command)
    result = processor.extract_osmnote("#osmnotetest")
    assert result is None, "Should not match #osmnote when followed by text without space"
    
    # But with space it should work
    result2 = processor.extract_osmnote("#osmnote test")
    assert result2 == "test"
    
    # Edge case: at end of string should work
    result3 = processor.extract_osmnote("#osmnote")
    assert result3 == ""


def test_osmnote_empty_text(processor, db, position_cache):
    """Test osmnote with empty text."""
    node_id = "test_node"
    position_cache.update(node_id, 1.0, 2.0)
    
    cmd_type, response = processor.process_message(node_id, "#osmnote")
    assert cmd_type == "osmnote_reject"
    assert "Falta el texto" in response


def test_osmnote_no_gps(processor, db):
    """Test osmnote without GPS."""
    node_id = "test_node"
    
    cmd_type, response = processor.process_message(node_id, "#osmnote test message")
    assert cmd_type == "osmnote_reject"
    assert "no hay GPS" in response


def test_osmnote_stale_gps(processor, db, position_cache):
    """Test osmnote with stale GPS."""
    from gateway.config import POS_MAX
    node_id = "test_node"
    position_cache.update(node_id, 1.0, 2.0)
    # Simulate old position (older than POS_MAX)
    position_cache.positions[node_id].received_at = time.time() - (POS_MAX + 10)
    
    cmd_type, response = processor.process_message(node_id, "#osmnote test")
    assert cmd_type == "osmnote_reject"
    assert "muy vieja" in response


def test_osmnote_success(processor, db, position_cache):
    """Test successful osmnote."""
    node_id = "test_node"
    position_cache.update(node_id, 1.0, 2.0)
    
    cmd_type, response = processor.process_message(node_id, "#osmnote test message")
    assert cmd_type == "osmnote_queued"
    assert response.startswith("Q-")


def test_osmnote_duplicate(processor, db, position_cache):
    """Test duplicate detection."""
    node_id = "test_node"
    position_cache.update(node_id, 1.0, 2.0)
    
    # First note
    cmd_type1, response1 = processor.process_message(node_id, "#osmnote test")
    assert cmd_type1 == "osmnote_queued"
    
    # Duplicate (same text, same location, same time bucket)
    cmd_type2, response2 = processor.process_message(node_id, "#osmnote test")
    assert cmd_type2 == "osmnote_duplicate"


def test_osmhelp(processor):
    """Test #osmhelp command."""
    cmd_type, response = processor.process_message("test_node", "#osmhelp")
    assert cmd_type == "osmhelp"
    assert response is not None
    assert "#osmnote" in response

def test_osmmorehelp(processor):
    """Test #osmmorehelp command."""
    cmd_type, response = processor.process_message("test_node", "#osmmorehelp")
    assert cmd_type == "osmmorehelp"
    assert response is not None
    assert "Canned Messages" in response or "mensajes predefinidos" in response
    assert "Para crear una nota" in response


def test_osmstatus(processor):
    """Test #osmstatus command."""
    cmd_type, response = processor.process_message("test_node", "#osmstatus")
    assert cmd_type == "osmstatus"
    assert "Gateway activo" in response


def test_osmcount(processor, db):
    """Test #osmcount command."""
    node_id = "test_node"
    
    # Create some notes
    db.create_note(node_id, 1.0, 2.0, "test1", "test1")
    db.create_note(node_id, 1.0, 2.0, "test2", "test2")
    
    cmd_type, response = processor.process_message(node_id, "#osmcount")
    assert cmd_type == "osmcount"
    assert response is not None
    assert "Total: 2" in response


def test_osmlist(processor, db):
    """Test #osmlist command."""
    node_id = "test_node"
    
    # Create some notes
    db.create_note(node_id, 1.0, 2.0, "test1", "test1")
    db.create_note(node_id, 1.0, 2.0, "test2", "test2")
    
    cmd_type, response = processor.process_message(node_id, "#osmlist")
    assert cmd_type == "osmlist"
    assert "notas:" in response


def test_osmqueue(processor, db):
    """Test #osmqueue command."""
    node_id = "test_node"
    
    # Create pending note
    db.create_note(node_id, 1.0, 2.0, "test", "test")
    
    cmd_type, response = processor.process_message(node_id, "#osmqueue")
    assert cmd_type == "osmqueue"
    assert response is not None
    assert "Cola:" in response


def test_osmnote_rate_limiting(processor, position_cache):
    """Test that rate limiting is applied to osmnote commands."""
    node_id = "test_node"
    position_cache.update(node_id, 4.6097, -74.0817)
    
    from gateway.config import USER_RATE_LIMIT_MAX_MESSAGES
    
    # Send messages up to limit
    for i in range(USER_RATE_LIMIT_MAX_MESSAGES):
        cmd_type, response = processor.process_message(node_id, f"#osmnote test {i}")
        assert cmd_type == "osmnote_queued"
    
    # Next message should be rate limited
    cmd_type, response = processor.process_message(node_id, "#osmnote test final")
    assert cmd_type == "osmnote_reject"
    assert "Límite de mensajes" in response


def test_osmnote_no_rate_limit_on_help(processor):
    """Test that help commands are not rate limited."""
    node_id = "test_node"
    
    # Send many help commands - should all work
    for i in range(10):
        cmd_type, response = processor.process_message(node_id, "#osmhelp")
        assert cmd_type == "osmhelp"
        assert response is not None
