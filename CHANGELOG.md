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

## [0.2.0] - 2026-04-13
### Added
- `nest_auth_setup.py` — interactive OAuth setup wizard (rclone-style):
  - Prompts for all credentials with inline hints on where to find each value;
    if an existing config is found, current values are shown as defaults and
    can be accepted with Enter
  - Generates and prints the browser authorization URL (includes `prompt=consent`
    to guarantee a fresh refresh token regardless of prior authorizations)
  - Accepts the full redirect URL (or bare code) and parses the authorization
    code automatically — no manual URL parsing required
  - Exchanges the code for tokens via the Google token endpoint
  - Writes `/etc/zabbix/nest_to_zabbix.conf` atomically with `600` permissions
    owned by the `zabbix` OS user
  - Detects if not running as root and exits with a clear `sudo` instruction
    before prompting for any credentials
  - Confirms the integration works by calling the SDM API and printing all
    discovered thermostat device IDs and room names
### Fixed
- Authorization URL now includes `prompt=consent` — without this parameter
  Google omits the `refresh_token` from the token response for accounts that
  have previously authorized the app, causing silent setup failure
### Changed
- README Part 1 restructured: Steps 1.1–1.4 remain as manual console steps;
  Step 1.5 is now the wizard invocation with the old manual flow preserved in
  a collapsible `<details>` block for reference
- README Troubleshooting section updated: primary recovery path is now
  `sudo python3 scripts/nest_auth_setup.py`; manual curl steps moved into a
  collapsible block
- README Step 2.2 updated to note that the wizard satisfies this step
- Both manual authorization URLs in README updated to include `prompt=consent`
  with an explanatory note

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
