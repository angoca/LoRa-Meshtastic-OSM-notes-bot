"""Tests for automatic time correction functionality."""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from gateway.database import Database
from gateway.main import Gateway


@pytest.fixture
def db(tmp_path):
    """Create temporary database."""
    db_path = tmp_path / "test.db"
    return Database(db_path=db_path)


def test_startup_timestamp_storage(db):
    """Test storing and retrieving startup timestamp."""
    timestamp = time.time()
    
    # Initially should be None
    assert db.get_startup_timestamp() is None
    
    # Set timestamp
    db.set_startup_timestamp(timestamp)
    
    # Should retrieve the same timestamp
    retrieved = db.get_startup_timestamp()
    assert retrieved is not None
    assert abs(retrieved - timestamp) < 1.0  # Allow small floating point differences


def test_time_correction_applied_flag(db):
    """Test time correction applied flag."""
    # Initially should be False
    assert db.get_time_correction_applied() is False
    
    # Set to True
    db.set_time_correction_applied(True)
    assert db.get_time_correction_applied() is True
    
    # Set to False
    db.set_time_correction_applied(False)
    assert db.get_time_correction_applied() is False


def test_adjust_pending_notes_timestamps_no_pending(db):
    """Test adjusting timestamps when there are no pending notes."""
    # Create a sent note (should not be adjusted)
    db.create_note("node1", 1.0, 2.0, "test", "test")
    # Mark as sent
    with db._get_connection() as conn:
        conn.execute("UPDATE notes SET status = 'sent' WHERE node_id = 'node1'")
        conn.commit()
    
    # Try to adjust (should adjust 0 notes)
    adjusted = db.adjust_pending_notes_timestamps(3600.0)
    assert adjusted == 0


def test_adjust_pending_notes_timestamps_with_pending(db):
    """Test adjusting timestamps of pending notes."""
    # Create pending notes
    note1_id = db.create_note("node1", 1.0, 2.0, "test1", "test1")
    note2_id = db.create_note("node2", 3.0, 4.0, "test2", "test2")
    
    # Get original timestamps
    with db._get_connection() as conn:
        cursor = conn.execute("SELECT created_at FROM notes WHERE local_queue_id = ?", (note1_id,))
        original_time1 = cursor.fetchone()["created_at"]
        
        cursor = conn.execute("SELECT created_at FROM notes WHERE local_queue_id = ?", (note2_id,))
        original_time2 = cursor.fetchone()["created_at"]
    
    # Adjust by 2 hours (7200 seconds)
    offset = 7200.0
    adjusted = db.adjust_pending_notes_timestamps(offset)
    assert adjusted == 2
    
    # Verify timestamps were adjusted
    with db._get_connection() as conn:
        cursor = conn.execute("SELECT created_at FROM notes WHERE local_queue_id = ?", (note1_id,))
        new_time1 = cursor.fetchone()["created_at"]
        
        cursor = conn.execute("SELECT created_at FROM notes WHERE local_queue_id = ?", (note2_id,))
        new_time2 = cursor.fetchone()["created_at"]
    
    # Parse timestamps and verify difference
    orig_dt1 = datetime.fromisoformat(original_time1)
    new_dt1 = datetime.fromisoformat(new_time1)
    diff1 = (new_dt1 - orig_dt1).total_seconds()
    assert abs(diff1 - offset) < 1.0  # Allow small floating point differences
    
    orig_dt2 = datetime.fromisoformat(original_time2)
    new_dt2 = datetime.fromisoformat(new_time2)
    diff2 = (new_dt2 - orig_dt2).total_seconds()
    assert abs(diff2 - offset) < 1.0


def test_adjust_pending_notes_timestamps_ignores_sent(db):
    """Test that sent notes are not adjusted."""
    # Create notes
    pending_id = db.create_note("node1", 1.0, 2.0, "pending", "pending")
    sent_id = db.create_note("node2", 3.0, 4.0, "sent", "sent")
    
    # Mark one as sent
    with db._get_connection() as conn:
        conn.execute("UPDATE notes SET status = 'sent' WHERE local_queue_id = ?", (sent_id,))
        conn.commit()
    
    # Get original timestamp of sent note
    with db._get_connection() as conn:
        cursor = conn.execute("SELECT created_at FROM notes WHERE local_queue_id = ?", (sent_id,))
        original_sent_time = cursor.fetchone()["created_at"]
    
    # Adjust timestamps
    offset = 3600.0
    adjusted = db.adjust_pending_notes_timestamps(offset)
    assert adjusted == 1  # Only pending note adjusted
    
    # Verify sent note timestamp was NOT changed
    with db._get_connection() as conn:
        cursor = conn.execute("SELECT created_at FROM notes WHERE local_queue_id = ?", (sent_id,))
        new_sent_time = cursor.fetchone()["created_at"]
    
    assert original_sent_time == new_sent_time


def test_adjust_pending_notes_timestamps_small_offset(db):
    """Test that small offsets (< 1 second) are ignored."""
    # Create pending note
    note_id = db.create_note("node1", 1.0, 2.0, "test", "test")
    
    # Try to adjust with small offset (0.5 seconds)
    adjusted = db.adjust_pending_notes_timestamps(0.5)
    assert adjusted == 0
    
    # Try with negative small offset
    adjusted = db.adjust_pending_notes_timestamps(-0.3)
    assert adjusted == 0


def test_adjust_pending_notes_timestamps_negative_offset(db):
    """Test adjusting timestamps with negative offset."""
    # Create pending note
    note_id = db.create_note("node1", 1.0, 2.0, "test", "test")
    
    # Get original timestamp
    with db._get_connection() as conn:
        cursor = conn.execute("SELECT created_at FROM notes WHERE local_queue_id = ?", (note_id,))
        original_time = cursor.fetchone()["created_at"]
    
    # Adjust by -1 hour (negative offset)
    offset = -3600.0
    adjusted = db.adjust_pending_notes_timestamps(offset)
    assert adjusted == 1
    
    # Verify timestamp was adjusted backwards
    with db._get_connection() as conn:
        cursor = conn.execute("SELECT created_at FROM notes WHERE local_queue_id = ?", (note_id,))
        new_time = cursor.fetchone()["created_at"]
    
    orig_dt = datetime.fromisoformat(original_time)
    new_dt = datetime.fromisoformat(new_time)
    diff = (new_dt - orig_dt).total_seconds()
    assert abs(diff - offset) < 1.0


@patch('gateway.main.subprocess.run')
def test_is_ntp_synchronized_true(mock_subprocess):
    """Test NTP synchronization check when synchronized."""
    # Mock timedatectl output indicating synchronization
    mock_subprocess.return_value = Mock(
        returncode=0,
        stdout="System clock synchronized: yes\nNTP service: active"
    )
    
    gateway = Gateway()
    assert gateway._is_ntp_synchronized() is True
    mock_subprocess.assert_called_once()


@patch('gateway.main.subprocess.run')
def test_is_ntp_synchronized_false(mock_subprocess):
    """Test NTP synchronization check when not synchronized."""
    # Mock timedatectl output indicating no synchronization
    mock_subprocess.return_value = Mock(
        returncode=0,
        stdout="System clock synchronized: no\nNTP service: inactive"
    )
    
    gateway = Gateway()
    assert gateway._is_ntp_synchronized() is False


@patch('gateway.main.subprocess.run')
def test_is_ntp_synchronized_error(mock_subprocess):
    """Test NTP synchronization check when command fails."""
    # Mock subprocess error
    mock_subprocess.side_effect = FileNotFoundError("timedatectl not found")
    
    gateway = Gateway()
    assert gateway._is_ntp_synchronized() is False


@patch('gateway.main.Gateway._is_ntp_synchronized')
def test_check_and_apply_time_correction_not_synchronized(mock_ntp_check):
    """Test that correction is not applied when NTP is not synchronized."""
    mock_ntp_check.return_value = False
    
    gateway = Gateway()
    gateway._check_and_apply_time_correction()
    
    # Should not mark correction as applied
    assert gateway.db.get_time_correction_applied() is False


@patch('gateway.main.Gateway._is_ntp_synchronized')
@patch('time.time')
def test_check_and_apply_time_correction_small_offset(mock_time, mock_ntp_check):
    """Test that correction is not applied for small offsets (< 60s)."""
    mock_ntp_check.return_value = True
    
    gateway = Gateway()
    startup_ts = time.time() - 30  # Only 30 seconds offset
    gateway.db.set_startup_timestamp(startup_ts)
    mock_time.return_value = time.time()
    
    gateway._check_and_apply_time_correction()
    
    # Should mark as applied but not actually adjust (small offset)
    assert gateway.db.get_time_correction_applied() is True


@patch('gateway.main.Gateway._is_ntp_synchronized')
@patch('time.time')
def test_check_and_apply_time_correction_large_offset(mock_time, mock_ntp_check):
    """Test that correction is applied for large offsets (> 60s)."""
    mock_ntp_check.return_value = True
    
    gateway = Gateway()
    current_time = time.time()
    startup_ts = current_time - 7200  # 2 hours offset
    gateway.db.set_startup_timestamp(startup_ts)
    mock_time.return_value = current_time
    
    # Create pending note
    note_id = gateway.db.create_note("node1", 1.0, 2.0, "test", "test")
    
    # Get original timestamp
    with gateway.db._get_connection() as conn:
        cursor = conn.execute("SELECT created_at FROM notes WHERE local_queue_id = ?", (note_id,))
        original_time = cursor.fetchone()["created_at"]
    
    gateway._check_and_apply_time_correction()
    
    # Should mark as applied
    assert gateway.db.get_time_correction_applied() is True
    
    # Verify note timestamp was adjusted
    with gateway.db._get_connection() as conn:
        cursor = conn.execute("SELECT created_at FROM notes WHERE local_queue_id = ?", (note_id,))
        new_time = cursor.fetchone()["created_at"]
    
    # Timestamps should be different (adjusted by ~7200 seconds)
    assert original_time != new_time


@patch('gateway.main.Gateway._is_ntp_synchronized')
def test_check_and_apply_time_correction_already_applied(mock_ntp_check):
    """Test that correction is not applied twice."""
    mock_ntp_check.return_value = True
    
    gateway = Gateway()
    gateway.db.set_time_correction_applied(True)
    
    # Create pending note
    note_id = gateway.db.create_note("node1", 1.0, 2.0, "test", "test")
    
    # Get original timestamp
    with gateway.db._get_connection() as conn:
        cursor = conn.execute("SELECT created_at FROM notes WHERE local_queue_id = ?", (note_id,))
        original_time = cursor.fetchone()["created_at"]
    
    gateway._check_and_apply_time_correction()
    
    # Verify note timestamp was NOT changed (already applied)
    with gateway.db._get_connection() as conn:
        cursor = conn.execute("SELECT created_at FROM notes WHERE local_queue_id = ?", (note_id,))
        new_time = cursor.fetchone()["created_at"]
    
    assert original_time == new_time


@patch('gateway.main.Gateway._is_ntp_synchronized')
@patch('time.time')
def test_check_and_apply_time_correction_only_pending(mock_time, mock_ntp_check):
    """Test that only pending notes are adjusted, not sent notes."""
    mock_ntp_check.return_value = True
    
    gateway = Gateway()
    current_time = time.time()
    startup_ts = current_time - 7200  # 2 hours offset
    gateway.db.set_startup_timestamp(startup_ts)
    mock_time.return_value = current_time
    
    # Create both pending and sent notes
    pending_id = gateway.db.create_note("node1", 1.0, 2.0, "pending", "pending")
    sent_id = gateway.db.create_note("node2", 3.0, 4.0, "sent", "sent")
    
    # Mark one as sent
    with gateway.db._get_connection() as conn:
        conn.execute("UPDATE notes SET status = 'sent' WHERE local_queue_id = ?", (sent_id,))
        conn.commit()
    
    # Get original timestamps
    with gateway.db._get_connection() as conn:
        cursor = conn.execute("SELECT created_at FROM notes WHERE local_queue_id = ?", (pending_id,))
        original_pending_time = cursor.fetchone()["created_at"]
        
        cursor = conn.execute("SELECT created_at FROM notes WHERE local_queue_id = ?", (sent_id,))
        original_sent_time = cursor.fetchone()["created_at"]
    
    gateway._check_and_apply_time_correction()
    
    # Verify pending note was adjusted
    with gateway.db._get_connection() as conn:
        cursor = conn.execute("SELECT created_at FROM notes WHERE local_queue_id = ?", (pending_id,))
        new_pending_time = cursor.fetchone()["created_at"]
        
        cursor = conn.execute("SELECT created_at FROM notes WHERE local_queue_id = ?", (sent_id,))
        new_sent_time = cursor.fetchone()["created_at"]
    
    assert original_pending_time != new_pending_time
    assert original_sent_time == new_sent_time  # Sent note not adjusted
