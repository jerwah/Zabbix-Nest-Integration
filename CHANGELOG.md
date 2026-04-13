# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Version numbers follow [Semantic Versioning](https://semver.org/):
- **MAJOR** version — incompatible changes (e.g. 2.0.0)
- **MINOR** version — new features, backwards compatible (e.g. 1.1.0)
- **PATCH** version — bug fixes only (e.g. 1.0.1)

---

## [Unreleased]

---

## [0.1.3] - 2026-04-13
### Fixed
- Automatic refresh token rotation: if Google returns a new `refresh_token` alongside
  an access token (token rotation), the script now persists it back to the config file
  atomically. Previously the rotated token was discarded, causing an `invalid_grant`
  error after sufficient time or API activity.
### Added
- README Troubleshooting section with step-by-step re-authorization instructions for
  the `invalid_grant` / token-expired scenario.

---

## [0.1.2] - 2026-04-05
### Changed
- README restructured for improved readability and flow

---

## [0.1.1] - 2026-04-05
### Added
- AI disclaimer to README

---

## [0.1.0] - 2026-04-05
### Added
- Python helper script (`nest_to_zabbix.py`) using Google SDM API with stdlib only (no third-party dependencies)
- OAuth 2.0 authentication via Web application client with refresh token
- Metrics: `current_temp`, `set_temp`, `humidity`, `mode` (with eco mode support)
- `--list-devices` flag showing device resource names and Google Home room names
- Per-invocation device data cache (`/tmp/nest_zabbix_<id>.json`, 5-minute TTL) with global lock to prevent concurrent API floods
- Clear, actionable error messages for HTTP 429 rate limit responses
- Zabbix 7.x YAML template: 4 items, 5 triggers, 2 graphs, 6 macros (importable, tested on 7.4.8)
- Config example (`nest_to_zabbix.conf.example`) with README label comments for each field
- `.gitignore` blocking credential files from version control
- Full setup README: Google Cloud project → OAuth consent screen → credentials → Device Access enrollment → authorization flow → Zabbix deployment (Steps 1.1–2.4)
