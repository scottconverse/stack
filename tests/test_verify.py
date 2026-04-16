"""
Tests for scripts/verify.py

All path arguments are injectable so tests never touch ~/.claude.
verify.py must not read from home directory at module import time.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import verify


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_settings(tmp_path, session_end=None, user_prompt=None,
                  pre_tool=None, mcp=None):
    hooks = {}
    if session_end is not None:
        hooks["SessionEnd"] = session_end
    if user_prompt is not None:
        hooks["UserPromptSubmit"] = user_prompt
    if pre_tool is not None:
        hooks["PreToolUse"] = pre_tool
    data = {"hooks": hooks}
    if mcp is not None:
        data["mcpServers"] = mcp
    p = tmp_path / "settings.json"
    p.write_text(json.dumps(data))
    return p


def make_cc_config(tmp_path, mcp=None):
    data = {}
    if mcp is not None:
        data["mcpServers"] = mcp
    p = tmp_path / ".claude.json"
    p.write_text(json.dumps(data))
    return p


def make_hooks_dir(tmp_path, files=None):
    d = tmp_path / "hooks"
    d.mkdir(exist_ok=True)
    for name, content in (files or {}).items():
        (d / name).write_text(content)
    return d


def wrapped(command):
    return {"hooks": [{"type": "command", "command": command}]}


def ctx_hook(matcher):
    """A PreToolUse hook entry for the given matcher, routed through context-mode."""
    return {
        "matcher": matcher,
        "hooks": [{"type": "command", "command": "node /path/to/context-mode/start.js"}],
    }


def hardgate_entry(script_path):
    """A PreToolUse hook entry that wires a hardgate script."""
    return {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": str(script_path)}],
    }


# ── check_longhand_session_end ────────────────────────────────────────────────

def test_longhand_session_end_present(tmp_path):
    s = make_settings(tmp_path, session_end=[wrapped("longhand ingest-session")])
    assert verify.check_longhand_session_end(s)["ok"] is True


def test_longhand_session_end_missing(tmp_path):
    s = make_settings(tmp_path, session_end=[])
    r = verify.check_longhand_session_end(s)
    assert r["ok"] is False
    assert "longhand setup" in r["fix"]


def test_longhand_session_end_no_hooks_key(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{}")
    assert verify.check_longhand_session_end(p)["ok"] is False


def test_longhand_session_end_file_missing(tmp_path):
    r = verify.check_longhand_session_end(tmp_path / "nonexistent.json")
    assert r["ok"] is False
    assert "missing" in r["fix"].lower() or "not found" in r["fix"].lower()


def test_longhand_session_end_malformed(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{ not json }")
    assert verify.check_longhand_session_end(p)["ok"] is False


# ── check_longhand_prompt_hook ────────────────────────────────────────────────

def test_longhand_prompt_hook_present(tmp_path):
    s = make_settings(tmp_path, user_prompt=[wrapped("longhand __prompt-hook-run")])
    assert verify.check_longhand_prompt_hook(s)["ok"] is True


def test_longhand_prompt_hook_missing(tmp_path):
    s = make_settings(tmp_path, user_prompt=[])
    r = verify.check_longhand_prompt_hook(s)
    assert r["ok"] is False
    assert "longhand prompt-hook install" in r["fix"]


# ── check_context_mode_hooks ──────────────────────────────────────────────────

def test_context_mode_hooks_three_required_matchers(tmp_path):
    """Three matchers including all required ones is the minimum acceptable."""
    s = make_settings(tmp_path, pre_tool=[
        ctx_hook("Bash"), ctx_hook("Read"), ctx_hook("WebFetch"),
    ])
    r = verify.check_context_mode_hooks(s)
    assert r["ok"] is True
    assert r["count"] == 3


def test_context_mode_hooks_nine_matchers(tmp_path):
    matchers = ["Bash", "Read", "WebFetch", "Grep", "Agent",
                "mcp__git", "mcp__npm", "mcp__pytest", "mcp__pip"]
    s = make_settings(tmp_path, pre_tool=[ctx_hook(m) for m in matchers])
    r = verify.check_context_mode_hooks(s)
    assert r["ok"] is True
    assert r["count"] == 9


def test_context_mode_hooks_partial_count_is_failure(tmp_path):
    """Only 1 context-mode matcher — count threshold not met."""
    s = make_settings(tmp_path, pre_tool=[ctx_hook("Bash")])
    r = verify.check_context_mode_hooks(s)
    assert r["ok"] is False
    assert r["count"] == 1


def test_context_mode_hooks_missing_required_matcher(tmp_path):
    """Three matchers but WebFetch is missing — required set not satisfied."""
    s = make_settings(tmp_path, pre_tool=[
        ctx_hook("Bash"), ctx_hook("Read"), ctx_hook("Grep"),
    ])
    r = verify.check_context_mode_hooks(s)
    assert r["ok"] is False
    assert "WebFetch" in r["detail"]


def test_context_mode_hooks_duplicate_matchers_is_failure(tmp_path):
    """Duplicate Bash entries from a double-install must fail, not pass."""
    s = make_settings(tmp_path, pre_tool=[
        ctx_hook("Bash"), ctx_hook("Bash"), ctx_hook("Read"),
        ctx_hook("WebFetch"),
    ])
    r = verify.check_context_mode_hooks(s)
    assert r["ok"] is False
    assert "duplicate" in r["detail"].lower()


def test_context_mode_hooks_missing(tmp_path):
    s = make_settings(tmp_path, pre_tool=[])
    assert verify.check_context_mode_hooks(s)["ok"] is False


def test_context_mode_hooks_two_matchers_is_failure(tmp_path):
    s = make_settings(tmp_path, pre_tool=[ctx_hook("Bash"), ctx_hook("Read")])
    assert verify.check_context_mode_hooks(s)["ok"] is False


# ── check_longhand_mcp ────────────────────────────────────────────────────────

def test_longhand_mcp_in_cc_config(tmp_path):
    cc = make_cc_config(tmp_path, mcp={"longhand": {"command": "longhand"}})
    s = make_settings(tmp_path)
    assert verify.check_longhand_mcp(s, cc)["ok"] is True


def test_longhand_mcp_in_settings(tmp_path):
    s = make_settings(tmp_path, mcp={"longhand": {"command": "longhand"}})
    cc = make_cc_config(tmp_path)
    assert verify.check_longhand_mcp(s, cc)["ok"] is True


def test_longhand_mcp_missing(tmp_path):
    s = make_settings(tmp_path)
    cc = make_cc_config(tmp_path, mcp={})
    r = verify.check_longhand_mcp(s, cc)
    assert r["ok"] is False
    assert "claude mcp add longhand" in r["fix"]


# ── check_context_mode_mcp ────────────────────────────────────────────────────

def test_context_mode_mcp_in_settings(tmp_path):
    s = make_settings(tmp_path, mcp={"context-mode": {"command": "node"}})
    cc = make_cc_config(tmp_path)
    assert verify.check_context_mode_mcp(s, cc)["ok"] is True


def test_context_mode_mcp_in_cc_config(tmp_path):
    s = make_settings(tmp_path)
    cc = make_cc_config(tmp_path, mcp={"context-mode": {"command": "node"}})
    assert verify.check_context_mode_mcp(s, cc)["ok"] is True


def test_context_mode_mcp_missing(tmp_path):
    s = make_settings(tmp_path)
    cc = make_cc_config(tmp_path)
    r = verify.check_context_mode_mcp(s, cc)
    assert r["ok"] is False
    assert "node install.js" in r["fix"]


# ── check_hardgate_artifacts ──────────────────────────────────────────────────

HARDGATE_SCRIPT_CONTENT = "#!/bin/bash\n# hardgate enforcement block\nexit 2\n"


def test_hardgate_present_and_wired(tmp_path):
    """Script with hardgate content exists AND is wired in settings.json."""
    hooks_dir = make_hooks_dir(tmp_path, {
        "enforce-context-mode.sh": HARDGATE_SCRIPT_CONTENT,
    })
    script_path = hooks_dir / "enforce-context-mode.sh"
    s = make_settings(tmp_path, pre_tool=[hardgate_entry(script_path)])
    r = verify.check_hardgate_artifacts(s, hooks_dir)
    assert r["ok"] is True
    assert r["warn"] is True  # hardgate is always a warning, never a required pass


def test_hardgate_script_exists_but_not_wired(tmp_path):
    """Script exists with hardgate content but is not wired into settings.json hooks."""
    hooks_dir = make_hooks_dir(tmp_path, {
        "enforce-context-mode.sh": HARDGATE_SCRIPT_CONTENT,
    })
    s = make_settings(tmp_path, pre_tool=[])  # no wiring
    r = verify.check_hardgate_artifacts(s, hooks_dir)
    assert r["ok"] is False
    assert r["warn"] is True


def test_hardgate_absent_when_no_hardgate_content(tmp_path):
    """Unrelated hook scripts must not produce a false positive."""
    hooks_dir = make_hooks_dir(tmp_path, {
        "some-other-hook.sh": "#!/bin/bash\necho hello\n",
    })
    s = make_settings(tmp_path)
    r = verify.check_hardgate_artifacts(s, hooks_dir)
    assert r["ok"] is False
    assert r["warn"] is True


def test_hardgate_hooks_dir_absent(tmp_path):
    s = make_settings(tmp_path)
    r = verify.check_hardgate_artifacts(s, tmp_path / "nonexistent")
    assert r["ok"] is False
    assert r["warn"] is True
    assert "/hard-gate" in r["fix"]


def test_hardgate_empty_hooks_dir(tmp_path):
    hooks_dir = make_hooks_dir(tmp_path, {})
    s = make_settings(tmp_path)
    r = verify.check_hardgate_artifacts(s, hooks_dir)
    assert r["ok"] is False


# ── run() exit codes ──────────────────────────────────────────────────────────

def test_run_exits_2_on_malformed_settings(tmp_path):
    """Exit code 2: settings.json exists but is malformed."""
    p = tmp_path / "settings.json"
    p.write_text("{ broken")
    cc = make_cc_config(tmp_path)
    hooks = make_hooks_dir(tmp_path, {})
    assert verify.run(settings_path=p, cc_config_path=cc, hooks_dir=hooks) == 2


def test_run_exits_2_on_malformed_cc_config(tmp_path):
    """Exit code 2: .claude.json exists but is malformed."""
    s = make_settings(tmp_path)
    cc = tmp_path / ".claude.json"
    cc.write_text("{ broken")
    hooks = make_hooks_dir(tmp_path, {})
    assert verify.run(settings_path=s, cc_config_path=cc, hooks_dir=hooks) == 2


def test_run_exits_1_when_settings_missing(tmp_path):
    """Exit code 1 (not 2) when settings.json is simply absent."""
    cc = make_cc_config(tmp_path)
    hooks = make_hooks_dir(tmp_path, {})
    code = verify.run(
        settings_path=tmp_path / "nonexistent.json",
        cc_config_path=cc,
        hooks_dir=hooks,
    )
    assert code == 1


def test_run_exits_0_when_all_required_checks_pass(tmp_path):
    """Hardgate absent (warning) must not prevent exit 0."""
    matchers = ["Bash", "Read", "WebFetch", "Grep", "Agent",
                "mcp__git", "mcp__npm", "mcp__pytest", "mcp__pip"]
    s = make_settings(
        tmp_path,
        session_end=[wrapped("longhand ingest-session")],
        user_prompt=[wrapped("longhand __prompt-hook-run")],
        pre_tool=[ctx_hook(m) for m in matchers],
        mcp={"context-mode": {"command": "node"}},
    )
    cc = make_cc_config(tmp_path, mcp={"longhand": {"command": "longhand"}})
    hooks = make_hooks_dir(tmp_path, {})  # no hardgate — warning only
    assert verify.run(settings_path=s, cc_config_path=cc, hooks_dir=hooks) == 0
