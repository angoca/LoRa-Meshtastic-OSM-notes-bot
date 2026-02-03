"""GPS position cache."""

import time
import logging
from typing import Optional, Tuple, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """GPS position with metadata."""
    lat: float
    lon: float
    received_at: float
    seen_count: int = 1


class PositionCache:
    """
    In-memory cache for GPS positions by node.
    
    Stores the latest known position for each Meshtastic node, along with
    metadata like timestamp and update count. Used for GPS validation
    before creating OSM notes.
    
    Attributes:
        positions: Dictionary mapping node_id to Position objects
        
    Note:
        Cache is lost on restart. Positions are automatically updated
        when new GPS data is received. Age calculation uses current
        system time.
    """

    def __init__(self):
        self.positions: Dict[str, Position] = {}

    def update(self, node_id: str, lat: float, lon: float):
        """Update position for a node."""
        now = time.time()
        if node_id in self.positions:
            self.positions[node_id].lat = lat
            self.positions[node_id].lon = lon
            self.positions[node_id].received_at = now
            self.positions[node_id].seen_count += 1
        else:
            self.positions[node_id] = Position(
                lat=lat,
                lon=lon,
                received_at=now,
                seen_count=1,
            )
        logger.debug(f"Updated position for {node_id}: ({lat}, {lon})")

    def get(self, node_id: str) -> Optional[Position]:
        """Get latest position for a node."""
        return self.positions.get(node_id)

    def get_age(self, node_id: str) -> Optional[float]:
        """Get age of latest position in seconds."""
        pos = self.get(node_id)
        if pos:
            return time.time() - pos.received_at
        return None

    def clear(self):
        """Clear all positions."""
        self.positions.clear()
