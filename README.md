# stack · v1.1.2

**One skill to install them all.**

`/stack` installs [Longhand](https://github.com/Wynelson94/longhand),
[Context-Mode](https://github.com/scottconverse/context-mode), and
[Hardgate](https://github.com/scottconverse/hardgate) as a coordinated
Claude Code stack — with timestamped config backup, per-tool idempotency
guards, and a hardened post-install verification checklist.

## Requirements

- Python 3.10+
- Node.js 18+
- Claude Code CLI (`claude` on PATH) — the standalone installer will offer to install this via npm if missing
- The full `stack` repo cloned locally

## Install

```bash
git clone https://github.com/scottconverse/stack
cd stack
```

**Option A — Standalone installer (no Claude Code session needed):**

```bash
# macOS / Linux
bash install.sh

# Windows — double-click install.bat, or from Git Bash:
python install.py
```

**Option B — Claude Code skill (from inside an active session):**

Add `skills/stack.md` to your Claude Code skill path, open a session, and run `/stack`.

> **Do not copy just `skills/stack.md` to `~/.claude/skills/`.**
> The skill requires `scripts/verify.py` to be present. Clone the
> full repo. The skill finds `verify.py` automatically via three-stage
> discovery (env var → plugin cache → bounded home search).

## What it installs

| Tool | What it does |
|------|-------------|
| **Longhand** | Stores every session verbatim in SQLite + ChromaDB. Semantic recall in ~126ms, zero API cost. |
| **Context-Mode** | Sandboxes tool output. Keeps raw command results off the context window. |
| **Hardgate** | Blocks forbidden tool calls via `exit 2` hooks. Requires one interactive step. |

## What happens

1. **Phase 0** — locates `verify.py` using env var → plugin cache → bounded find
2. **Pre-flight** — checks Python, Node, and tool locations. Takes timestamped
   snapshots of `~/.claude/settings.json` and `~/.claude.json`.
3. **Idempotency** — checks ALL required artifacts per tool; only skips if
   a tool is fully installed.
4. **Install** — Longhand → Context-Mode → Hardgate (guided).
5. **Post-verify** — `scripts/verify.py` checks specific expected hook
   matchers, wiring, and MCP entries. Restores both config snapshots if
   either is malformed.

## Known limitation

The verifier checks that config entries are *present*, not that MCP
servers are *live*. After install, run:

```bash
longhand doctor
claude mcp list
```

to verify runtime health.

## Tested versions

This repo was validated against these versions. Behavior with other
versions is untested.

| Tool | Tested version |
|------|---------------|
| Longhand | 0.5.5 |
| Context-Mode | 1.6.0 |
| Python | 3.14.3 (pre-release; 3.10+ supported) |
| Node.js | 18+ |

Pin Longhand if you need a reproducible install:

```bash
pip install longhand==0.5.5
```

Context-Mode is installed from a local clone — pin by checking out the
validated commit hash before running `node install.js`.

## Running the verifier standalone

```bash
python scripts/verify.py
```

## Tests

```bash
pip install pytest
pytest tests/ -v
```

75 tests covering all verifier logic, exit codes, and installer behaviour.

## License

MIT
