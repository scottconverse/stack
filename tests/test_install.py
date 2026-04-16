"""
Tests for install.py

Module-level path constants (SETTINGS, CC_CONFIG, HOOKS_DIR, HOME) are
monkeypatched to tmp_path so tests never touch ~/.claude.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import install
import verify


# ── Shared fixtures ────────────────────────────────────────────────────────────

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
    return {
        "matcher": matcher,
        "hooks": [{"type": "command", "command": "node /path/to/context-mode/start.js"}],
    }


def hardgate_entry(script_path):
    return {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": str(script_path)}],
    }


HARDGATE_CONTENT  = "#!/bin/bash\n# hardgate enforcement block\nexit 2\n"
ALL_CTX_MATCHERS  = ["Bash", "Read", "WebFetch", "Grep", "Agent",
                     "mcp__git", "mcp__npm", "mcp__pytest", "mcp__pip"]


# ── _run() ─────────────────────────────────────────────────────────────────────

def test_run_success_returns_0():
    code = install._run([sys.executable, "-c", "import sys; sys.exit(0)"])
    assert code == 0


def test_run_failure_returns_nonzero():
    code = install._run([sys.executable, "-c", "import sys; sys.exit(1)"])
    assert code != 0


def test_run_dumps_output_to_stdout_on_failure(capsys):
    install._run([sys.executable, "-c",
                  "print('captured error detail'); import sys; sys.exit(1)"])
    out = capsys.readouterr().out
    assert "captured error detail" in out


def test_run_suppresses_output_on_success(capsys):
    install._run([sys.executable, "-c", "print('should not appear')"])
    out = capsys.readouterr().out
    assert "should not appear" not in out


# ── is_longhand_complete() ─────────────────────────────────────────────────────

def test_longhand_complete_when_all_artifacts_present(tmp_path, monkeypatch):
    s = make_settings(
        tmp_path,
        session_end=[wrapped("longhand ingest-session")],
        user_prompt=[wrapped("longhand __prompt-hook-run")],
        mcp={"longhand": {"command": "longhand"}},
    )
    cc = make_cc_config(tmp_path)
    monkeypatch.setattr(install, "SETTINGS", s)
    monkeypatch.setattr(install, "CC_CONFIG", cc)
    with patch("shutil.which", return_value="/usr/bin/longhand"):
        assert install.is_longhand_complete(verify) is True


def test_longhand_incomplete_when_binary_missing(tmp_path, monkeypatch):
    s = make_settings(
        tmp_path,
        session_end=[wrapped("longhand ingest-session")],
        user_prompt=[wrapped("longhand __prompt-hook-run")],
        mcp={"longhand": {"command": "longhand"}},
    )
    cc = make_cc_config(tmp_path)
    monkeypatch.setattr(install, "SETTINGS", s)
    monkeypatch.setattr(install, "CC_CONFIG", cc)
    with patch("shutil.which", return_value=None):
        assert install.is_longhand_complete(verify) is False


def test_longhand_incomplete_when_settings_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(install, "SETTINGS", tmp_path / "nonexistent.json")
    monkeypatch.setattr(install, "CC_CONFIG", tmp_path / "nonexistent.json")
    with patch("shutil.which", return_value="/usr/bin/longhand"):
        assert install.is_longhand_complete(verify) is False


# ── is_context_mode_complete() ─────────────────────────────────────────────────

def test_context_mode_complete_when_all_artifacts_present(tmp_path, monkeypatch):
    s = make_settings(
        tmp_path,
        pre_tool=[ctx_hook(m) for m in ALL_CTX_MATCHERS],
        mcp={"context-mode": {"command": "node"}},
    )
    cc = make_cc_config(tmp_path)
    monkeypatch.setattr(install, "SETTINGS", s)
    monkeypatch.setattr(install, "CC_CONFIG", cc)
    assert install.is_context_mode_complete(verify) is True


def test_context_mode_incomplete_when_hooks_missing(tmp_path, monkeypatch):
    s = make_settings(tmp_path, pre_tool=[])
    cc = make_cc_config(tmp_path)
    monkeypatch.setattr(install, "SETTINGS", s)
    monkeypatch.setattr(install, "CC_CONFIG", cc)
    assert install.is_context_mode_complete(verify) is False


def test_context_mode_incomplete_when_mcp_missing(tmp_path, monkeypatch):
    s = make_settings(tmp_path, pre_tool=[ctx_hook(m) for m in ALL_CTX_MATCHERS])
    cc = make_cc_config(tmp_path, mcp={})  # no context-mode entry
    monkeypatch.setattr(install, "SETTINGS", s)
    monkeypatch.setattr(install, "CC_CONFIG", cc)
    assert install.is_context_mode_complete(verify) is False


# ── is_hardgate_complete() ─────────────────────────────────────────────────────

def test_hardgate_complete_when_script_and_wiring_present(tmp_path, monkeypatch):
    hooks_dir = make_hooks_dir(tmp_path, {"enforce.sh": HARDGATE_CONTENT})
    script_path = hooks_dir / "enforce.sh"
    s = make_settings(tmp_path, pre_tool=[hardgate_entry(script_path)])
    monkeypatch.setattr(install, "SETTINGS", s)
    monkeypatch.setattr(install, "HOOKS_DIR", hooks_dir)
    assert install.is_hardgate_complete(verify) is True


def test_hardgate_incomplete_when_script_exists_but_not_wired(tmp_path, monkeypatch):
    hooks_dir = make_hooks_dir(tmp_path, {"enforce.sh": HARDGATE_CONTENT})
    s = make_settings(tmp_path, pre_tool=[])  # script present but not wired
    monkeypatch.setattr(install, "SETTINGS", s)
    monkeypatch.setattr(install, "HOOKS_DIR", hooks_dir)
    assert install.is_hardgate_complete(verify) is False


def test_hardgate_incomplete_when_hooks_dir_absent(tmp_path, monkeypatch):
    s = make_settings(tmp_path)
    monkeypatch.setattr(install, "SETTINGS", s)
    monkeypatch.setattr(install, "HOOKS_DIR", tmp_path / "nonexistent")
    assert install.is_hardgate_complete(verify) is False


def test_hardgate_incomplete_when_empty_hooks_dir(tmp_path, monkeypatch):
    hooks_dir = make_hooks_dir(tmp_path, {})
    s = make_settings(tmp_path)
    monkeypatch.setattr(install, "SETTINGS", s)
    monkeypatch.setattr(install, "HOOKS_DIR", hooks_dir)
    assert install.is_hardgate_complete(verify) is False


# ── _find_context_mode_dir() ───────────────────────────────────────────────────

def test_find_context_mode_dir_finds_plugin_cache(tmp_path, monkeypatch):
    cache = tmp_path / ".claude" / "plugins" / "cache" / "context-mode"
    cache.mkdir(parents=True)
    (cache / "install.js").write_text("// install")
    monkeypatch.setattr(install, "HOME", tmp_path)
    assert install._find_context_mode_dir() == cache


def test_find_context_mode_dir_finds_at_depth2(tmp_path, monkeypatch):
    # ~/projects/context-mode/install.js
    d = tmp_path / "projects" / "context-mode"
    d.mkdir(parents=True)
    (d / "install.js").write_text("// install")
    monkeypatch.setattr(install, "HOME", tmp_path)
    assert install._find_context_mode_dir() == d


def test_find_context_mode_dir_finds_at_depth3(tmp_path, monkeypatch):
    # ~/dev/tools/context-mode/install.js
    d = tmp_path / "dev" / "tools" / "context-mode"
    d.mkdir(parents=True)
    (d / "install.js").write_text("// install")
    monkeypatch.setattr(install, "HOME", tmp_path)
    assert install._find_context_mode_dir() == d


def test_find_context_mode_dir_returns_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(install, "HOME", tmp_path)
    assert install._find_context_mode_dir() is None


def test_find_context_mode_dir_ignores_dirs_without_install_js(tmp_path, monkeypatch):
    # Dir named context-mode but no install.js
    d = tmp_path / "projects" / "context-mode"
    d.mkdir(parents=True)
    (d / "readme.md").write_text("no installer here")
    monkeypatch.setattr(install, "HOME", tmp_path)
    assert install._find_context_mode_dir() is None


def test_find_context_mode_dir_ignores_unrelated_dirs_with_install_js(tmp_path, monkeypatch):
    # install.js exists but dir is not named context-mode
    d = tmp_path / "projects" / "some-other-tool"
    d.mkdir(parents=True)
    (d / "install.js").write_text("// install")
    monkeypatch.setattr(install, "HOME", tmp_path)
    assert install._find_context_mode_dir() is None


def test_find_context_mode_dir_prefers_plugin_cache_over_home_walk(tmp_path, monkeypatch):
    # Both cache and home-walk match — cache should win (checked first)
    cache = tmp_path / ".claude" / "plugins" / "cache" / "context-mode"
    cache.mkdir(parents=True)
    (cache / "install.js").write_text("// cache version")

    other = tmp_path / "projects" / "context-mode"
    other.mkdir(parents=True)
    (other / "install.js").write_text("// home walk version")

    monkeypatch.setattr(install, "HOME", tmp_path)
    assert install._find_context_mode_dir() == cache
