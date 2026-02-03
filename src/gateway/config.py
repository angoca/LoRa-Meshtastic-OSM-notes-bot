"""Configuration management."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directory for data
DATA_DIR = Path(os.getenv("DATA_DIR", "/var/lib/lora-osmnotes"))
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except (PermissionError, OSError):
    # Fallback to temp directory if we don't have permissions (e.g., during tests)
    import tempfile
    DATA_DIR = Path(tempfile.gettempdir()) / "lora-osmnotes-test"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

# Database path
DB_PATH = DATA_DIR / "gateway.db"

# Serial port
SERIAL_PORT = os.getenv("SERIAL_PORT", "/dev/ttyACM0")

# Dry run mode
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Timezone
TZ = os.getenv("TZ", "America/Bogota")

# GPS validation thresholds (seconds)
POS_GOOD = 15
POS_MAX = 60

# Deduplication settings
DEDUP_TIME_BUCKET_SECONDS = 120
DEDUP_LOCATION_PRECISION = 4  # decimal places for lat/lon

# OSM API
OSM_API_URL = "https://api.openstreetmap.org/api/0.6/notes.json"
OSM_RATE_LIMIT_SECONDS = 3

# Worker intervals (seconds)
WORKER_INTERVAL = 30
NOTIFICATION_ANTI_SPAM_WINDOW = 60  # seconds
NOTIFICATION_ANTI_SPAM_MAX = 3  # max notifications per window

# Daily broadcast (optional)
DAILY_BROADCAST_ENABLED = os.getenv("DAILY_BROADCAST_ENABLED", "false").lower() == "true"
