# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added
- Comprehensive `README.md` with setup instructions for Docker and Unraid
- `CHANGELOG.md` (this file)
- `CONTRIBUTING.md` with contributor guidelines
- `.env.example` template with all available options documented

### Fixed
- **Config reload after restart:** Settings saved through the web UI now also update `os.environ` immediately, ensuring values are visible to the running process and are correctly persisted to `/config/.env` for the next startup.
- **Boolean settings not saved:** The `update_config` handler now correctly saves `false` values (e.g., `TELEGRAM_ENABLED=false`) that were previously skipped due to a falsy-value check.
- **Admin password change:** Changing the admin password via the web UI now takes effect immediately in the current session without requiring a restart to log in with the new password.

---

## [2026-03-17]

### Added
- Web-based configuration and management UI (port 2759)
- Fernet-encrypted admin password storage
- Activity dashboard with post history and delivery statistics
- Real-time log viewer
- One-click container restart from the web UI
- Unified `/config` mount point for configuration, logs, and data
- Support for both generic Docker Compose and Unraid deployments
- Self-signed TLS certificate auto-generated on first start
- Bluesky credentials optional at startup — configure via web UI

### Changed
- Bluesky, Telegram, and Discord clients are now skipped at startup if credentials are not configured, preventing startup failures on a fresh install.

### Fixed
- Container no longer loses its network connection when Bluesky login fails; the web UI remains accessible for configuration.
