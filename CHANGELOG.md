# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning: [Semantic Versioning](https://semver.org/).

## [1.1.0] — 2026-04-16

### Added
- `install.py` — standalone installer; installs Longhand and Context-Mode
  without requiring an open Claude Code session. Guides Hardgate interactively.
  Shares `scripts/verify.py` with the skill for identical post-install checks.
- `install.bat` — Windows double-click launcher for `install.py`
- `install.sh` — macOS / Linux launcher for `install.py`
- `install.py --verify` flag to run post-install verification only
- Cross-platform context-mode discovery (Python-native walk, no `find` dependency)
- ANSI colour output with automatic fallback for legacy Windows terminals

## [1.0.0] — 2026-04-16

### Added
- `/stack` skill — installs Longhand, Context-Mode, and Hardgate in sequence
- Three-stage verify.py discovery: env var → plugin cache → bounded home find
- Pre-flight checks Python 3.10+, Node 18+, and tool locations
- Timestamped snapshots of both `~/.claude/settings.json` and `~/.claude.json`
  (`.stack-backup-YYYYMMDD-HHMMSS`); reruns do not overwrite prior backups
- Per-tool idempotency: skips only when ALL required artifacts are present
- Session state persisted to `~/.claude/stack-session.env` before Hardgate
  pause so `VERIFY_PY` and `STACK_TS` survive the interaction boundary
- `scripts/verify.py` — post-install verifier with symmetric exit-2 corruption
  handling for both config files; catches both `JSONDecodeError` and `OSError`
- Context-Mode check verifies specific required matchers (Bash, Read, WebFetch)
  are present and detects duplicate entries
- Hardgate check verifies both script existence (by content) and hook wiring
  in settings.json — orphaned scripts do not produce false positives
- Restore hint uses `ls -t ... | head -1` — deterministic with multiple backups
- Known-limitation notice: config presence does not equal MCP liveness
- Tested-version matrix: Longhand 0.5.5, Context-Mode 1.6.0, Python 3.14.3
- 29 unit tests covering all verifier logic and exit codes
