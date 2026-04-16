#!/usr/bin/env python3
"""
Post-install verifier for the stack installer.

Reads ~/.claude/settings.json and ~/.claude.json, checks that each
expected hook and MCP entry is present, and prints a result checklist.

Exit codes:
  0 — all required checks passed (Hardgate warning is acceptable)
  1 — one or more required checks failed, or settings.json is absent
  2 — settings.json OR .claude.json exists but is malformed (restore from backup)

Known limitation: this verifier checks config entries, not live MCP
server status. Run `longhand doctor` and `claude mcp list` after install
to verify runtime health.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


# Context-Mode matchers that must be present for a valid install.
# A partial install missing any of these is a failure, not a warning.
REQUIRED_CTX_MATCHERS = {"Bash", "Read", "WebFetch"}


# ── JSON helpers ──────────────────────────────────────────────────────────────

def _load(path: Path) -> dict | None:
    """Return parsed JSON or None if the file is missing or unreadable."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _command_str(entry: Any) -> str:
    """Extract all command text from a hook entry (wrapped or flat format)."""
    if not isinstance(entry, dict):
        return ""
    inner = entry.get("hooks")
    if isinstance(inner, list):
        return " ".join(
            h.get("command", "") for h in inner if isinstance(h, dict)
        )
    return entry.get("command", "")


def _hook_list_contains(entries: list, needle: str) -> bool:
    return any(needle in _command_str(e) for e in entries)


# ── Individual checks ─────────────────────────────────────────────────────────

def check_longhand_session_end(settings_path: Path) -> dict:
    data = _load(settings_path)
    if data is None:
        return {
            "ok": False,
            "label": "Longhand SessionEnd hook",
            "fix": "settings.json missing or unreadable — run: longhand setup",
        }
    entries = data.get("hooks", {}).get("SessionEnd", [])
    ok = _hook_list_contains(entries, "longhand ingest-session")
    return {
        "ok": ok,
        "label": "Longhand SessionEnd hook",
        "fix": "Run: longhand setup",
    }


def check_longhand_prompt_hook(settings_path: Path) -> dict:
    data = _load(settings_path)
    if data is None:
        return {
            "ok": False,
            "label": "Longhand UserPromptSubmit hook",
            "fix": "settings.json missing or unreadable — run: longhand setup",
        }
    entries = data.get("hooks", {}).get("UserPromptSubmit", [])
    ok = _hook_list_contains(entries, "__prompt-hook-run")
    return {
        "ok": ok,
        "label": "Longhand UserPromptSubmit hook",
        "fix": "Run: longhand prompt-hook install",
    }


def check_context_mode_hooks(settings_path: Path) -> dict:
    """Require >=3 context-mode PreToolUse matchers, all required ones present,
    no duplicates.

    Counting is not sufficient. The required matchers (Bash, Read, WebFetch)
    must all be present. Duplicate matchers from a double-install must fail
    rather than inflate the count.
    """
    data = _load(settings_path)
    if data is None:
        return {
            "ok": False,
            "label": "Context-Mode PreToolUse hooks",
            "count": 0,
            "detail": "settings.json missing",
            "fix": "Run: node install.js  (from your context-mode directory)",
        }
    entries = data.get("hooks", {}).get("PreToolUse", [])
    ctx_entries = [e for e in entries if "context-mode" in _command_str(e)]
    count = len(ctx_entries)

    matchers = [
        e.get("matcher", "") for e in ctx_entries if isinstance(e, dict)
    ]
    named = [m for m in matchers if m]
    has_duplicates = len(named) != len(set(named))
    matcher_set = set(named)
    missing_required = REQUIRED_CTX_MATCHERS - matcher_set

    problems = []
    if count < 3:
        problems.append(f"only {count} matchers (need >=3)")
    if missing_required:
        problems.append(f"missing required: {', '.join(sorted(missing_required))}")
    if has_duplicates:
        problems.append("duplicate matchers detected — re-run node install.js")

    ok = count >= 3 and not missing_required and not has_duplicates
    return {
        "ok": ok,
        "label": "Context-Mode PreToolUse hooks",
        "count": count,
        "detail": "; ".join(problems) if problems else None,
        "fix": "Run: node install.js  (from your context-mode directory)",
    }


def check_longhand_mcp(settings_path: Path, cc_config_path: Path) -> dict:
    cc = _load(cc_config_path) or {}
    settings = _load(settings_path) or {}
    ok = (
        "longhand" in cc.get("mcpServers", {})
        or "longhand" in settings.get("mcpServers", {})
    )
    return {
        "ok": ok,
        "label": "Longhand MCP server",
        "fix": "Run: claude mcp add longhand -s user -- longhand mcp-server",
    }


def check_context_mode_mcp(settings_path: Path, cc_config_path: Path) -> dict:
    cc = _load(cc_config_path) or {}
    settings = _load(settings_path) or {}
    ok = (
        "context-mode" in cc.get("mcpServers", {})
        or "context-mode" in settings.get("mcpServers", {})
    )
    return {
        "ok": ok,
        "label": "Context-Mode MCP server",
        "fix": "Run: node install.js  (from your context-mode directory)",
    }


def check_hardgate_artifacts(settings_path: Path, hooks_dir: Path) -> dict:
    """Check that a hardgate script exists AND is wired into settings.json hooks.

    Checking content (not just filename) avoids false positives from
    unrelated scripts. Checking wiring ensures the script is actually
    enforced, not just sitting orphaned in the hooks directory.

    Always returns warn=True — Hardgate requires interactive setup and
    the stack functions without it, but the consequence is named explicitly.
    """
    # Step 1: find scripts with hardgate content
    hardgate_scripts: list[Path] = []
    if hooks_dir.exists():
        for sh in hooks_dir.glob("*.sh"):
            try:
                if "hardgate" in sh.read_text(errors="ignore").lower():
                    hardgate_scripts.append(sh)
            except OSError:
                pass

    if not hardgate_scripts:
        return {
            "ok": False,
            "warn": True,
            "label": "Hardgate enforcement",
            "fix": "Run /hard-gate and select context-mode as the enforcement target",
        }

    # Step 2: verify at least one is wired in settings.json
    data = _load(settings_path) or {}
    all_entries: list[dict] = []
    for event_hooks in data.get("hooks", {}).values():
        if isinstance(event_hooks, list):
            all_entries.extend(event_hooks)

    def _is_wired(script: Path) -> bool:
        name = script.name
        full = str(script)
        return any(
            name in _command_str(e) or full in _command_str(e)
            for e in all_entries
        )

    wired = any(_is_wired(s) for s in hardgate_scripts)
    return {
        "ok": wired,
        "warn": True,
        "label": "Hardgate enforcement",
        "fix": "Run /hard-gate and select context-mode as the enforcement target",
    }


# ── Report ────────────────────────────────────────────────────────────────────

def print_report(results: list[dict]) -> int:
    BAR = "─" * 45
    print(f"\nStack install results")
    print(BAR)

    failures = []
    for r in results:
        label = r["label"]
        if r["ok"]:
            extra = f" ({r['count']} matchers)" if "count" in r else ""
            print(f"✓  {label}{extra}")
        elif r.get("warn"):
            print(f"⚠  {label} — enforcement layer inactive")
            print(f"   Fix: {r['fix']}")
        else:
            detail = f" ({r['detail']})" if r.get("detail") else ""
            print(f"✗  {label}{detail}")
            failures.append(r)

    print(BAR)

    if failures:
        print("\nFailed — retry commands:")
        for f in failures:
            print(f"  • {f['fix']}")
        print()
        return 1

    if any(not r["ok"] for r in results):
        print("Required checks passed. Complete Hardgate to activate enforcement.\n")
    else:
        print("Installation complete. Restart Claude Code to activate all changes.\n")

    print("Note: this verifier checks config presence, not live MCP server status.")
    print("Run 'longhand doctor' and 'claude mcp list' to verify runtime health.\n")
    return 0


# ── Main ──────────────────────────────────────────────────────────────────────

def run(
    settings_path: Path | None = None,
    cc_config_path: Path | None = None,
    hooks_dir: Path | None = None,
) -> int:
    settings_path = settings_path or Path.home() / ".claude" / "settings.json"
    cc_config_path = cc_config_path or Path.home() / ".claude.json"
    hooks_dir = hooks_dir or Path.home() / ".claude" / "hooks"

    # Guard: if either config file exists but is malformed, exit 2 immediately.
    # Missing files degrade gracefully to failed checks (exit 1).
    for cfg, label in [(settings_path, "settings.json"), (cc_config_path, ".claude.json")]:
        if cfg.exists():
            try:
                json.loads(cfg.read_text())
            except (json.JSONDecodeError, OSError) as e:
                print(f"✗  {label} is malformed or unreadable at {cfg} ({e})")
                print(f"   Find backup: ls -t {cfg}.stack-backup-* 2>/dev/null | head -1")
                print(f"   Restore:     cp $(ls -t {cfg}.stack-backup-* | head -1) {cfg}")
                return 2

    results = [
        check_longhand_session_end(settings_path),
        check_longhand_prompt_hook(settings_path),
        check_context_mode_hooks(settings_path),
        check_longhand_mcp(settings_path, cc_config_path),
        check_context_mode_mcp(settings_path, cc_config_path),
        check_hardgate_artifacts(settings_path, hooks_dir),
    ]
    return print_report(results)


if __name__ == "__main__":
    sys.exit(run())
