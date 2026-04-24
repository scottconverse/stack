# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- Tested-versions table in `README.md` refreshed to current upstream:
  Longhand `0.5.5` → `0.8.1`, Context-Mode `1.6.0` → `1.6.1`.
- Added explicit **Last validated** date line (2026-04-24) to README.
- Longhand pin example bumped to `pip install longhand==0.8.1`.

### Notes
- stack's pytest suite passes 75/75 against current `scripts/verify.py`.
- Longhand install surfaces stack invokes (`longhand setup`,
  `prompt-hook install`, `mcp-server`) are unchanged across the
  0.5.5 → 0.8.1 range per upstream CHANGELOG — additive changes only
  (`reconcile` MCP tool, staleness detection, recall narrative fixes).
- End-to-end `install.py` run was not re-exercised against these
  specific versions during this refresh. No code changes to
  `install.py` or `scripts/verify.py`.

## [1.1.2] — 2026-04-16

### Fixed
- `install.py`: version defined once as `__version__` constant; banner and
  docstring now reference it — eliminates version drift on every release
- `verify.py` `_command_str()`: now handles string-format hook entries
  (previously silently returned `""`, causing missed matches)
- `verify.py` `print_report()`: warning-branch condition made explicit
  (`r.get("warn")`) so logic does not rely on implicit ordering
- `verify.py`: stale Hardgate fix message ("select context-mode as the
  enforcement target") replaced with neutral "follow the prompts" wording
- `install.py` `_find_context_mode_dir()`: content validation added —
  `install.js` must reference "context-mode" or "context_mode" to match;
  prevents false positives from unrelated projects named context-mode
- `install.py` `_find_context_mode_dir()`: exclusion list skips common
  system/tool directories (`.cargo`, `.npm`, `AppData`, `Library`, etc.)
  for significantly faster discovery on developer machines
- `install.py` `is_hardgate_complete()`: exception handling broadened to
  catch `TypeError`, `AttributeError`, and other unexpected errors from
  malformed hook data — not only `NotADirectoryError` and `OSError`
- `install.py` `_run()`: `cwd` type annotation corrected to
  `str | Path | None` (was `str | None`)
- `CONTRIBUTING.md`: test count corrected (was "50", then "59"; now 75)

### Added
- `tests/conftest.py`: shared fixtures extracted from both test files —
  eliminates duplication that was a maintenance hazard
- 16 new tests: `_is_context_mode_install_js()` (4), `backup_configs()` (3),
  `restore_configs()` (2), `--verify` flag (1), `_command_str()` string
  format (3), Hardgate fix message wording (1), string-format hook
  recognition in `check_longhand_session_end` (1), content-validation
  rejection in `_find_context_mode_dir` (1)
- Total test count: 59 → 75

## [1.1.1] — 2026-04-16

### Fixed
- `install.py` subprocess output now captured and shown only on failure —
  eliminates verbose pip/node noise on successful installs
- Hardgate idempotency: re-running the installer no longer pauses for
  the interactive `/hard-gate` step when Hardgate is already configured
- Hardgate instructions no longer prescribe a specific enforcement target;
  users are directed to follow the prompts and choose for themselves
- Context-Mode "not found" prompt moved to the prerequisites phase so all
  missing-dependency questions appear together before installation starts
- Node.js missing: installer now shows the platform-specific install
  command (`winget` / `brew` / `apt`) instead of a bare URL
- Claude Code CLI missing: installer offers to run
  `npm install -g @anthropic-ai/claude-code` rather than failing immediately
- 30 new unit tests covering `_run()`, idempotency helpers,
  `_find_context_mode_dir()`, plus adversarial cases (nonexistent commands,
  malformed JSON, depth limits, HOOKS_DIR-as-file) — total: 29 → 59

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
