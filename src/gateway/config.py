"""Configuration management."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
# Try to load from standard locations
env_paths = [
    Path("/var/lib/lora-osmnotes/.env"),  # Production location
    Path(".env"),  # Current directory
    Path(__file__).parent.parent.parent / ".env",  # Project root
]
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        break
else:
    # Fallback: try default load_dotenv() behavior
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

# GPS validation bypass (for debugging - set to true to disable GPS freshness checks)
# Default: false (GPS validation enabled)
GPS_VALIDATION_DISABLED = os.getenv("GPS_VALIDATION_DISABLED", "false").lower() == "true"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Timezone
TZ = os.getenv("TZ", "America/Bogota")

# GPS validation thresholds (seconds)
# POS_GOOD: Position is considered "good" if less than this age
# POS_MAX: Maximum acceptable position age (reject if older)
# Note: With minimum broadcast interval of 60s, we allow up to 120s to account
# for mesh network latency and timing variations
POS_GOOD = 15
POS_MAX = 120  # Increased from 60 to 120 seconds to accommodate 60s broadcast minimum

# Deduplication settings
DEDUP_TIME_BUCKET_SECONDS = 120
DEDUP_LOCATION_PRECISION = 4  # decimal places for lat/lon

# OSM API
OSM_API_URL = "https://api.openstreetmap.org/api/0.6/notes.json"
OSM_RATE_LIMIT_SECONDS = 3
OSM_MAX_RETRIES = 3  # Maximum retry attempts for failed OSM API calls
OSM_RETRY_DELAY_SECONDS = 60  # Delay between retries

# Nominatim reverse geocoding API
NOMINATIM_API_URL = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_RATE_LIMIT_SECONDS = 1  # Nominatim requires max 1 request per second
NOMINATIM_TIMEOUT = 5  # seconds

# Meshtastic message limits
MESHTASTIC_MAX_MESSAGE_LENGTH = 200  # Safe limit (theoretical max is ~237 bytes)

# Rate limiting per user
USER_RATE_LIMIT_WINDOW = 60  # seconds
USER_RATE_LIMIT_MAX_MESSAGES = 5  # max messages per window per user

# Device uptime thresholds (seconds)
DEVICE_UPTIME_RECENT = 120  # Device is "recently started" if uptime < this
DEVICE_UPTIME_GPS_WAIT = 60  # Wait time for GPS fix after device start

# Worker intervals (seconds)
WORKER_INTERVAL = 30
NOTIFICATION_ANTI_SPAM_WINDOW = 60  # seconds
NOTIFICATION_ANTI_SPAM_MAX = 3  # max notifications per window

# Daily broadcast (optional)
DAILY_BROADCAST_ENABLED = os.getenv("DAILY_BROADCAST_ENABLED", "false").lower() == "true"

# Internationalization (i18n)
LANGUAGE = os.getenv("LANGUAGE", "es")  # Default: Spanish

# Project information
PROJECT_NAME = "OSM Mesh Notes Gateway"
