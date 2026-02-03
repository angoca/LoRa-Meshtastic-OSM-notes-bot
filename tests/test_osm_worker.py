"""Tests for OSM worker."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import time
import sys

# Mock requests if not available
try:
    import requests
except ImportError:
    sys.modules['requests'] = MagicMock()

from gateway.osm_worker import OSMWorker
from gateway.database import Database


@pytest.fixture
def db(tmp_path):
    """Create temporary database."""
    db_path = tmp_path / "test.db"
    return Database(db_path=db_path)


@pytest.fixture
def worker(db):
    """Create OSM worker."""
    return OSMWorker(db)


def test_send_note_dry_run(worker, monkeypatch):
    """Test sending note in dry run mode."""
    monkeypatch.setenv("DRY_RUN", "true")
    # Reload config to pick up DRY_RUN
    import importlib
    import gateway.config
    importlib.reload(gateway.config)
    # Recreate worker to use new config
    from gateway.osm_worker import OSMWorker
    worker = OSMWorker(worker.db)
    
    result = worker.send_note(lat=1.0, lon=2.0, text="Test note")
    assert result is not None
    assert "id" in result
    assert "url" in result
    assert "openstreetmap.org" in result["url"]


@patch('gateway.osm_worker.requests.post')
def test_send_note_success(mock_post, worker, monkeypatch):
    """Test successful note sending."""
    monkeypatch.setenv("DRY_RUN", "false")
    import importlib
    import gateway.config
    importlib.reload(gateway.config)
    
    # Mock successful response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "properties": {"id": 12345}
    }
    mock_post.return_value = mock_response
    
    result = worker.send_note(lat=1.0, lon=2.0, text="Test note")
    
    assert result is not None
    assert result["id"] == 12345
    assert result["url"] == "https://www.openstreetmap.org/note/12345"
    mock_post.assert_called_once()


@patch('gateway.osm_worker.requests.post')
def test_send_note_api_error(mock_post, worker, monkeypatch):
    """Test API error handling."""
    monkeypatch.setenv("DRY_RUN", "false")
    import importlib
    import gateway.config
    importlib.reload(gateway.config)
    
    # Mock error response
    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    mock_post.return_value = mock_response
    
    result = worker.send_note(lat=1.0, lon=2.0, text="Test note")
    
    assert result is None


@patch('gateway.osm_worker.requests.post')
def test_send_note_timeout(mock_post, worker, monkeypatch):
    """Test timeout handling."""
    monkeypatch.setenv("DRY_RUN", "false")
    import importlib
    import gateway.config
    importlib.reload(gateway.config)
    
    import requests
    mock_post.side_effect = requests.exceptions.Timeout()
    
    result = worker.send_note(lat=1.0, lon=2.0, text="Test note")
    
    assert result is None


@patch('gateway.osm_worker.requests.post')
def test_send_note_connection_error(mock_post, worker, monkeypatch):
    """Test connection error handling."""
    monkeypatch.setenv("DRY_RUN", "false")
    import importlib
    import gateway.config
    importlib.reload(gateway.config)
    
    import requests
    mock_post.side_effect = requests.exceptions.ConnectionError()
    
    result = worker.send_note(lat=1.0, lon=2.0, text="Test note")
    
    assert result is None


@patch('gateway.osm_worker.OSMWorker.send_note')
def test_process_pending_success(mock_send, worker, db):
    """Test processing pending notes successfully."""
    # Create pending note
    queue_id = db.create_note("node1", 1.0, 2.0, "test", "test")
    
    # Mock successful send
    mock_send.return_value = {"id": 12345, "url": "https://osm.org/note/12345"}
    
    sent_count = worker.process_pending(limit=10)
    
    assert sent_count == 1
    # Verify note was updated
    note = db.get_note_by_queue_id(queue_id)
    assert note["status"] == "sent"
    assert note["osm_note_id"] == 12345


@patch('gateway.osm_worker.OSMWorker.send_note')
def test_process_pending_failure(mock_send, worker, db):
    """Test processing pending notes with failure."""
    # Create pending note
    queue_id = db.create_note("node1", 1.0, 2.0, "test", "test")
    
    # Mock failed send
    mock_send.return_value = None
    
    sent_count = worker.process_pending(limit=10)
    
    assert sent_count == 0
    # Verify note still pending
    note = db.get_note_by_queue_id(queue_id)
    assert note["status"] == "pending"
    assert note["last_error"] is not None


@patch('gateway.osm_worker.requests.post')
def test_rate_limiting(mock_post, worker, monkeypatch):
    """Test rate limiting."""
    monkeypatch.setenv("DRY_RUN", "false")
    import importlib
    import gateway.config
    importlib.reload(gateway.config)
    # Recreate worker to use new config
    from gateway.osm_worker import OSMWorker
    worker = OSMWorker(worker.db)
    
    import requests
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"properties": {"id": 1}}
    mock_post.return_value = mock_response
    
    start_time = time.time()
    result1 = worker.send_note(1.0, 2.0, "test1")
    result2 = worker.send_note(1.0, 2.0, "test2")
    elapsed = time.time() - start_time
    
    # Should have at least 3 seconds between sends (OSM_RATE_LIMIT_SECONDS)
    assert elapsed >= 2.5, f"Rate limiting not working: elapsed={elapsed}"  # Allow some margin
    assert result1 is not None
    assert result2 is not None
