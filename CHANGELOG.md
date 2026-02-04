# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- Installation script for Raspberry Pi OS
- Documentation (README, ARCHITECTURE, CONTRIBUTING, API, SECURITY, TROUBLESHOOTING)
- Canonical specification document (docs/spec.md)

### Security
- Non-root execution by default (User=nobody in systemd template)
- Auto-detection of service user in install script
- Security documentation and best practices

## [0.1.0] - 2026-02-02

### Added
- Initial release of MVP gateway
- Core functionality for Meshtastic → OSM Notes conversion
- Store-and-forward capability for offline operation
- Command interface via Meshtastic hashtags
- GPS validation and deduplication
- Notification system with privacy warnings

### Fixed
- Word boundary bug in `#osmnote` extraction (prevented false positives like `#osmnotetest`)
- Systemd service user configuration (auto-detection and fix script)
- Circular import in database module
- Test environment setup (permissions, mocking)

### Changed
- Moved documentation files to `docs/` directory for better organization
- Updated repository references to `https://github.com/OSM-Notes/osm-mesh-notes-gateway`
- Improved code documentation and docstrings

---

## Types of Changes

- **Added** for new features
- **Changed** for changes in existing functionality
- **Deprecated** for soon-to-be removed features
- **Removed** for now removed features
- **Fixed** for any bug fixes
- **Security** for vulnerability fixes
