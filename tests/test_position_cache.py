"""Tests for position cache."""

import pytest
import time
from gateway.position_cache import PositionCache


def test_update_and_get():
    """Test position update and retrieval."""
    cache = PositionCache()
    
    cache.update("node1", 1.0, 2.0)
    pos = cache.get("node1")
    
    assert pos is not None
    assert pos.lat == 1.0
    assert pos.lon == 2.0
    assert pos.seen_count == 1


def test_get_age():
    """Test position age calculation."""
    cache = PositionCache()
    
    cache.update("node1", 1.0, 2.0)
    age = cache.get_age("node1")
    
    assert age is not None
    assert age >= 0
    assert age < 1.0  # Should be very recent


def test_seen_count():
    """Test seen count increment."""
    cache = PositionCache()
    
    cache.update("node1", 1.0, 2.0)
    assert cache.get("node1").seen_count == 1
    
    cache.update("node1", 1.1, 2.1)
    assert cache.get("node1").seen_count == 2


def test_clear():
    """Test cache clearing."""
    cache = PositionCache()
    
    cache.update("node1", 1.0, 2.0)
    assert cache.get("node1") is not None
    
    cache.clear()
    assert cache.get("node1") is None
