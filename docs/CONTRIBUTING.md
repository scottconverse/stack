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

All 29 tests must pass before submitting a PR.

## Architecture

`skills/stack.md` — primary deliverable. Instructs Claude Code what to
do when `/stack` is invoked. Keep it prescriptive: exact commands, exact
expected output, no "handle errors appropriately" language.

`scripts/verify.py` — post-install state inspector. All path arguments
are injectable so tests never touch the real Claude config. When adding
a new check, write the test first.

## Distribution model

Users clone the full repo. Do not add a supported "copy just the skill
file" path — `verify.py` must travel with the skill.

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
