# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **New Command**: `#osmnodes` command to list all known nodes in the mesh network, showing node ID, GPS coordinates, time since last seen, and number of times seen. Useful for validating mesh connectivity and device presence.
- **Project Attribution**: OSM notes now include attribution text ("Created via OSM Mesh Notes Gateway") at the end, translated to the user's current language preference.

### Fixed
- Fixed missing `locale` parameter in `send_note` method that prevented project attribution from being translated correctly.
- Fixed "Interface not connected, cannot send broadcast" warning during daily broadcast attempts by checking connection status before sending.
- Improved message reception reliability by subscribing to pubsub topics *before* creating the SerialInterface, ensuring all messages are captured.
- Added fallback subscription to general `meshtastic.receive` topic to catch packets that might not be published to specific topics.

### Changed
- **Logging Configuration**: Changed default log level from DEBUG to INFO for production use. Meshtastic library logging is now set to WARNING level to reduce verbosity.
- **Message Delays**: Increased delay between multi-part messages (e.g., `#osmhelp`) from 1 second to 2 seconds to prevent message loss in the mesh network.
- **Documentation**: Updated `README.md` and help messages (`#osmhelp`, `#osmmorehelp`) to include `#osmnodes` command documentation.

### Technical Details
- Enhanced `MeshtasticSerial.start()` to subscribe to pubsub topics before connecting to ensure message capture.
- Added `_on_receive_all` method as a fallback handler for general `meshtastic.receive` topic, filtering by `portnum` and forwarding to appropriate handlers.
- Improved logging in `_on_receive_text` and `_on_receive_all` with INFO level messages for better debugging visibility.
- Added `is_connected()` method to `MeshtasticSerial` class for connection status checking.

## [0.1.1] - 2026-02-08

### Fixed
- **Critical**: Resolved `UnboundLocalError: cannot access local variable 'lat'` in `_handle_osmnote` method. The error occurred when GPS validation was enabled because `lat` and `lon` variables were only defined in certain code paths. Fixed by using `position.lat` and `position.lon` directly instead of intermediate variables.
- Fixed `MSG_ACK_SUCCESS() got an unexpected keyword argument 'locale'` error. Added `locale` parameter support to `MSG_ACK_SUCCESS` function to properly handle internationalization.
- Fixed "Data payload too big" errors when sending acknowledgment messages. Long confirmation messages are now automatically split into multiple parts using the existing `split_long_message` function, with appropriate delays between parts.

### Changed
- **User Experience**: Privacy warning message ("⚠️ No envíes datos personales ni emergencias de cualquier tipo") now appears only every 5 notes per user instead of in every message, reducing message repetition while still maintaining periodic reminders. The warning still appears in all error/rejection messages as they are less frequent.
- Modified `MSG_ACK_SUCCESS`, `MSG_ACK_QUEUED`, and `MSG_DUPLICATE` functions to accept an optional `show_warning` parameter (default: `True`) to control when the privacy warning is displayed.
- Updated `NotificationManager.send_ack` to calculate whether to show the warning based on the user's total note count (shows on notes 5, 10, 15, 20, etc.).

### Technical Details
- Improved error handling in `meshtastic_serial.py` with full traceback logging for better debugging.
- Enhanced message splitting logic to handle acknowledgment messages that exceed Meshtastic's payload size limits (233 bytes).
- Added anti-spam checks before sending multi-part acknowledgment messages to prevent notification flooding.

## [0.1.0] - 2026-02-03

### Added
- Initial MVP implementation
- Meshtastic USB serial communication with auto-reconnect
- GPS position caching and validation (POS_GOOD=15s, POS_MAX=60s)
- Command processing (#osmnote, #osmhelp, #osmstatus, #osmcount, #osmlist, #osmqueue)
- Deduplication logic (intra-node, 4 decimal precision, 120s time bucket)
- SQLite store-and-forward queue
- OSM Notes API integration with rate limiting (≥3s between sends)
- DM notification system with anti-spam (max 3/min/node)
- Systemd service configuration
- Comprehensive test suite with pytest
- Installation script for Raspberry Pi OS (`scripts/install_pi.sh`)
- Serial device detection script (`scripts/detect_serial.sh`)
- Documentation structure:
  - README.md (user-friendly, non-technical)
  - docs/spec.md (canonical specification)
  - docs/architecture.md (system architecture)
  - docs/message-format.md (Meshtastic message formats)
  - docs/API.md (internal API reference)
  - docs/SECURITY.md (security best practices)
  - docs/TROUBLESHOOTING.md (troubleshooting guide)
  - CONTRIBUTING.md (contribution guidelines)
- Project metadata files:
  - CHANGELOG.md (Keep a Changelog format)
  - CITATION.cff (citation metadata)
  - AUTHORS (authors and contributors)

### Security
- Non-root execution by default (User=nobody in systemd template)
- Auto-detection of service user in install script
- Security documentation and best practices

### Fixed
- Word boundary bug in `#osmnote` extraction (prevented false positives like `#osmnotetest`)
- Systemd service user configuration (auto-detection and fix script)
- Circular import in database module
- Test environment setup (permissions, mocking)

### Changed
- Moved documentation files to `docs/` directory for better organization
- Updated repository references to `https://github.com/OSM-Notes/osm-mesh-notes-gateway`
- Improved code documentation and docstrings
- Enhanced README.md for non-technical readers
- Added code formatting and linting tools (Black + Ruff)
- Established `pyproject.toml` as source of truth for dependencies

---

## Types of Changes

- **Added** for new features
- **Changed** for changes in existing functionality
- **Deprecated** for soon-to-be removed features
- **Removed** for now removed features
- **Fixed** for any bug fixes
- **Security** for vulnerability fixes
