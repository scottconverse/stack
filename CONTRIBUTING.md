# Contributing

## Setup

```bash
git clone https://github.com/scottconverse/stack
cd stack
pip install pytest
```

**Shell requirement:** Use Git Bash or WSL on Windows. The skill file
uses bash syntax throughout.

## Running tests

```bash
pytest tests/ -v
```

All 50 tests must pass before submitting a PR.

## Architecture

`install.py` — standalone installer (v1.1.0+). Installs Longhand,
Context-Mode, and Hardgate without requiring an open Claude Code session.
Uses only Python stdlib. Imports `scripts/verify.py` via
`importlib.util.spec_from_file_location` so the two share identical
post-install check logic. Context-Mode discovery uses a Python-native
directory walk — no `find` dependency — so it works on Windows without
Git Bash.

`install.bat` / `install.sh` — thin launchers for `install.py`. bat
passes `%*` args; sh passes `"$@"` and sets `set -e`.

`skills/stack.md` — Claude Code skill. Instructs Claude Code what to
do when `/stack` is invoked. Keep it prescriptive: exact commands, exact
expected output, no "handle errors appropriately" language.

`scripts/verify.py` — post-install state inspector. All path arguments
are injectable so tests never touch the real Claude config. When adding
a new check, write the test first. Shared by both `install.py` and the
`/stack` skill.

## Distribution model

Users clone the full repo. Do not add a supported "copy just the skill
file" path — `verify.py` must travel with the skill, and `install.py`
imports it by relative path.

## Backup naming

Backups use timestamped suffixes (`.stack-backup-YYYYMMDD-HHMMSS`).
Do not use fixed names — reruns must not overwrite prior backups.

## Session state

The skill persists `VERIFY_PY`, `STACK_TS`, and `CTX_DIR` to
`~/.claude/stack-session.env` before the Hardgate pause. Phase 3
sources this file to restore the variables. If you modify the pause
boundary, ensure all variables required by Phase 3 are written before
the pause.

## Commit style

```
feat: add X
fix: correct Y
chore: update Z
docs: update README
```

One logical change per commit.
