"""
Shared test helpers for test_verify.py and test_install.py.

Pytest automatically adds the tests/ directory to sys.path, so both
test files can import from here with `from conftest import ...`.
"""
import json
from pathlib import Path


HARDGATE_CONTENT = "#!/bin/bash\n# hardgate enforcement block\nexit 2\n"
ALL_CTX_MATCHERS = ["Bash", "Read", "WebFetch", "Grep", "Agent",
                    "mcp__git", "mcp__npm", "mcp__pytest", "mcp__pip"]


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
