# GitHub Discussions — Seeded Posts

Copy-paste these into the relevant GitHub Discussions categories after enabling
Discussions in repo Settings → General → Features → Discussions.

---

## 📣 Announcements — Pin this post

**Title:** Welcome to stack — what this is and where it's headed

---

Hey — Scott here. Thanks for checking this out.

`stack` started as a personal frustration: I kept manually wiring Longhand, Context-Mode, and Hardgate into every new machine and every new Claude Code setup, getting the hook ordering wrong, forgetting the backup step, and having no idea whether the install actually worked.

So I built a single skill that does all of it in the right order, with timestamped config backups, per-tool idempotency checks, and a post-install verifier that tells you exactly what passed and what to retry.

**Current state (v1.1.1):** Install-only, three tools, 75 tests, verified on Python 3.14.3 and Node 18+. Two install paths: `python install.py` (standalone, no active Claude Code session needed) and `/stack` (Claude Code skill). The verifier checks config wiring but not live MCP server health — `longhand doctor` and `claude mcp list` are still the runtime truth.

**What's coming:** Uninstall support, richer verifier output, and possibly support for additional tools in the stack. Nothing is on a hard timeline — this is a tool I use myself, and I ship when it's ready.

If you run into anything — install failures, unexpected behavior, a check that's wrong — open an issue or drop it in Q&A here. I read everything.

---

## ❓ Q&A — Seed post 1

**Title:** Do I need to clone the full repo, or can I just copy the skill file?

---

**You need to clone the full repo.**

The `/stack` skill file (`skills/stack.md`) depends on `scripts/verify.py` being present on your local machine. The skill locates `verify.py` through a three-stage discovery process: checking a `STACK_DIR` environment variable, searching the Claude plugin cache, and falling back to a bounded `find` across your home directory.

If `verify.py` can't be found, the skill stops with an error before doing anything else.

```bash
git clone https://github.com/scottconverse/stack
```

That's it — then open Claude Code and run `/stack`. The skill finds `verify.py` automatically from the cloned path.

The reason the verifier can't be bundled into the skill file itself: Claude Code skill files are Markdown, not executables, and the post-install verification step needs to run Python code that's too complex to inline as a heredoc reliably across platforms.

---

## ❓ Q&A — Seed post 2

**Title:** Can I run the installer again if something fails mid-install?

---

**Yes — both install paths are designed to be re-run safely.**

Before starting any installs, the installer checks which tools are already fully installed. "Fully" means every required artifact is present: the CLI tool, the hooks in `settings.json`, and the MCP server entry. If all artifacts for a tool are present, that tool is skipped. If any artifact is missing, the full installer for that tool runs again.

This means:
- If Longhand installed cleanly but Context-Mode failed, re-running skips Longhand and retries Context-Mode.
- If you run the installer on a machine where everything is already installed, it prints "fully installed — skipping" for each tool and goes straight to verification.

Each run also creates a new timestamped backup of your config files, so you can always roll back to any prior state:

```bash
ls -t ~/.claude/settings.json.stack-backup-* | head -1
```

---

## ❓ Q&A — Seed post 3

**Title:** What does the verifier actually check? What does a "pass" mean?

---

`scripts/verify.py` checks six things after install:

| Check | What it verifies |
|-------|-----------------|
| Longhand SessionEnd hook | `longhand ingest-session` is wired as a hook |
| Longhand UserPromptSubmit hook | `__prompt-hook-run` is wired as a hook |
| Context-Mode PreToolUse hooks | At least 3 matchers present, including Bash, Read, and WebFetch; no duplicates |
| Longhand MCP server | `longhand` appears in `mcpServers` in either config file |
| Context-Mode MCP server | `context-mode` appears in `mcpServers` |
| Hardgate enforcement | A `.sh` script with "hardgate" content is wired into hooks |

**What a pass means:** The config entries are correct. Claude Code will attempt to use these tools on the next session.

**What a pass does NOT mean:** That the MCP servers are actually running and responding. Config presence and runtime liveness are separate questions.

After the verifier exits 0, also run:

```bash
longhand doctor
claude mcp list
```

These tell you whether the processes are live, not just configured.

---

## 💡 Ideas — Seed post 1

**Title:** Uninstall support — should `/stack` know how to undo itself?

---

Right now `/stack` is install-only. Once the three tools are wired in, removing them requires manually editing `~/.claude/settings.json` and running `claude mcp remove`.

I've been thinking about an `/unstack` skill (or an `--uninstall` flag) that would:
1. Remove each tool's hooks from `settings.json`
2. Remove the MCP server entries
3. Leave the installed packages in place (pip uninstall / npm uninstall is the user's call)
4. Restore the pre-stack backup if one is present

The tricky part is that the hooks weren't created by a single installer with a manifest — they were written by three separate tools. A clean uninstall needs to know exactly what each tool's hooks look like so it doesn't accidentally remove something the user added manually.

Curious whether people would use this. Does a clean uninstall matter for your workflow, or is re-cloning and starting fresh good enough?

---

## 💡 Ideas — Seed post 2

**Title:** Expanding the stack — what other Claude Code tools belong here?

---

The current stack is opinionated: Longhand + Context-Mode + Hardgate is the combination I use and trust. But the orchestrator pattern isn't specific to these three tools.

If you're using other Claude Code tools that involve hook wiring or MCP server registration, I'm interested to hear about them. Questions I'd want to answer before adding anything:

- Does it have a clean programmatic install (not just "paste this JSON")?
- Does it produce verifiable artifacts we can check post-install?
- Does it interact safely with the existing three tools' hooks?

Not making promises — just want to understand what people are actually using alongside this stack before designing anything.

---

## 👋 General — Welcome post

**Title:** Welcome — how to get help and get involved

---

Welcome to the `stack` community.

**Getting started:**
- [README](https://github.com/scottconverse/stack/blob/master/README.md) — what this is and how to install it
- [User Manual](https://scottconverse.github.io/stack/USER-MANUAL.html) — plain-language guide including troubleshooting
- [CONTRIBUTING.md](https://github.com/scottconverse/stack/blob/master/CONTRIBUTING.md) — how to run tests and submit changes

**Getting help:**
- Installation problems → Q&A here or open an [issue](https://github.com/scottconverse/stack/issues)
- Unexpected verifier behavior → open an issue with the full verifier output (exit code + all lines)
- General questions → Q&A here

**Getting involved:**
- Found a bug? Check the [issues list](https://github.com/scottconverse/stack/issues) first, then open one if it's new
- Want to add a check to the verifier? Read the architecture notes in CONTRIBUTING.md — the pattern is TDD: write the failing test first, then the implementation
- Have a tool you think belongs in the stack? Drop it in Ideas

The test suite (`pytest tests/ -v`) runs in under a second from a clean clone. If you're contributing, run it before every commit — all 59 must pass.
