"""
Tests for install.py

Module-level path constants (SETTINGS, CC_CONFIG, HOOKS_DIR, HOME) are
monkeypatched to tmp_path so tests never touch ~/.claude.
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))
import install
import verify

from conftest import (
    make_settings, make_cc_config, make_hooks_dir,
    wrapped, ctx_hook, hardgate_entry,
    HARDGATE_CONTENT, ALL_CTX_MATCHERS,
)

# Content that passes _is_context_mode_install_js() validation
CTX_JS_CONTENT = "// context-mode MCP server installer\nmodule.exports = {};\n"
CTX_JS_CONTENT_UNDERSCORE = "// context_mode MCP server installer\nmodule.exports = {};\n"


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


# ── _is_context_mode_install_js() ─────────────────────────────────────────────

def test_is_context_mode_install_js_matches_hyphenated(tmp_path):
    f = tmp_path / "install.js"
    f.write_text(CTX_JS_CONTENT)
    assert install._is_context_mode_install_js(f) is True


def test_is_context_mode_install_js_matches_underscored(tmp_path):
    f = tmp_path / "install.js"
    f.write_text(CTX_JS_CONTENT_UNDERSCORE)
    assert install._is_context_mode_install_js(f) is True


def test_is_context_mode_install_js_rejects_unrelated_content(tmp_path):
    """install.js from an unrelated project must not match."""
    f = tmp_path / "install.js"
    f.write_text("// some completely unrelated tool\nmodule.exports = {};\n")
    assert install._is_context_mode_install_js(f) is False


def test_is_context_mode_install_js_handles_missing_file(tmp_path):
    f = tmp_path / "nonexistent.js"
    assert install._is_context_mode_install_js(f) is False


# ── _find_context_mode_dir() ───────────────────────────────────────────────────

def test_find_context_mode_dir_finds_plugin_cache(tmp_path, monkeypatch):
    cache = tmp_path / ".claude" / "plugins" / "cache" / "context-mode"
    cache.mkdir(parents=True)
    (cache / "install.js").write_text(CTX_JS_CONTENT)
    monkeypatch.setattr(install, "HOME", tmp_path)
    assert install._find_context_mode_dir() == cache


def test_find_context_mode_dir_finds_at_depth2(tmp_path, monkeypatch):
    # ~/projects/context-mode/install.js
    d = tmp_path / "projects" / "context-mode"
    d.mkdir(parents=True)
    (d / "install.js").write_text(CTX_JS_CONTENT)
    monkeypatch.setattr(install, "HOME", tmp_path)
    assert install._find_context_mode_dir() == d


def test_find_context_mode_dir_finds_at_depth3(tmp_path, monkeypatch):
    # ~/dev/tools/context-mode/install.js
    d = tmp_path / "dev" / "tools" / "context-mode"
    d.mkdir(parents=True)
    (d / "install.js").write_text(CTX_JS_CONTENT)
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
    (d / "install.js").write_text(CTX_JS_CONTENT)
    monkeypatch.setattr(install, "HOME", tmp_path)
    assert install._find_context_mode_dir() is None


def test_find_context_mode_dir_ignores_install_js_without_matching_content(tmp_path, monkeypatch):
    """Dir is named context-mode but install.js belongs to an unrelated project."""
    d = tmp_path / "projects" / "context-mode"
    d.mkdir(parents=True)
    (d / "install.js").write_text("// unrelated project installer")
    monkeypatch.setattr(install, "HOME", tmp_path)
    assert install._find_context_mode_dir() is None


def test_find_context_mode_dir_prefers_plugin_cache_over_home_walk(tmp_path, monkeypatch):
    # Both cache and home-walk match — cache should win (checked first)
    cache = tmp_path / ".claude" / "plugins" / "cache" / "context-mode"
    cache.mkdir(parents=True)
    (cache / "install.js").write_text(CTX_JS_CONTENT)

    other = tmp_path / "projects" / "context-mode"
    other.mkdir(parents=True)
    (other / "install.js").write_text(CTX_JS_CONTENT)

    monkeypatch.setattr(install, "HOME", tmp_path)
    assert install._find_context_mode_dir() == cache


def test_find_context_mode_dir_accepts_underscore_naming(tmp_path, monkeypatch):
    # context_mode (underscore) is an alternative naming convention
    d = tmp_path / "projects" / "context_mode"
    d.mkdir(parents=True)
    (d / "install.js").write_text(CTX_JS_CONTENT_UNDERSCORE)
    monkeypatch.setattr(install, "HOME", tmp_path)
    assert install._find_context_mode_dir() == d


def test_find_context_mode_dir_does_not_find_depth4(tmp_path, monkeypatch):
    # depth 4 is beyond the search limit — must return None
    deep = tmp_path / "a" / "b" / "c" / "context-mode"
    deep.mkdir(parents=True)
    (deep / "install.js").write_text(CTX_JS_CONTENT)
    monkeypatch.setattr(install, "HOME", tmp_path)
    assert install._find_context_mode_dir() is None


# ── Adversarial: _run() ────────────────────────────────────────────────────────

def test_run_nonexistent_command_returns_127():
    """FileNotFoundError must not propagate — returns 127 (command not found)."""
    code = install._run(["nonexistent-binary-xyz-abc-123"])
    assert code == 127


def test_run_nonexistent_command_prints_error(capsys):
    install._run(["nonexistent-binary-xyz-abc-123"])
    out = capsys.readouterr().out
    assert "not found" in out.lower() or "nonexistent" in out.lower()


def test_run_exits_nonzero_even_when_output_is_empty():
    """Silent failures (no stdout) still return non-zero exit code."""
    code = install._run([sys.executable, "-c", "import sys; sys.exit(2)"])
    assert code == 2


# ── Adversarial: idempotency helpers with malformed JSON ──────────────────────

def test_longhand_complete_returns_false_on_malformed_settings(tmp_path, monkeypatch):
    bad = tmp_path / "settings.json"
    bad.write_text("{ not valid json }")
    cc = make_cc_config(tmp_path)
    monkeypatch.setattr(install, "SETTINGS", bad)
    monkeypatch.setattr(install, "CC_CONFIG", cc)
    with patch("shutil.which", return_value="/usr/bin/longhand"):
        assert install.is_longhand_complete(verify) is False


def test_context_mode_complete_returns_false_on_malformed_settings(tmp_path, monkeypatch):
    bad = tmp_path / "settings.json"
    bad.write_text("{ not valid json }")
    cc = make_cc_config(tmp_path)
    monkeypatch.setattr(install, "SETTINGS", bad)
    monkeypatch.setattr(install, "CC_CONFIG", cc)
    assert install.is_context_mode_complete(verify) is False


def test_hardgate_complete_returns_false_on_malformed_settings(tmp_path, monkeypatch):
    bad = tmp_path / "settings.json"
    bad.write_text("{ not valid json }")
    hooks_dir = make_hooks_dir(tmp_path, {"enforce.sh": HARDGATE_CONTENT})
    monkeypatch.setattr(install, "SETTINGS", bad)
    monkeypatch.setattr(install, "HOOKS_DIR", hooks_dir)
    assert install.is_hardgate_complete(verify) is False


# ── Adversarial: is_hardgate_complete() with bad HOOKS_DIR ────────────────────

def test_hardgate_complete_returns_false_when_hooks_dir_is_a_file(tmp_path, monkeypatch):
    """HOOKS_DIR pointing to a file must not raise NotADirectoryError."""
    file_not_dir = tmp_path / "hooks"
    file_not_dir.write_text("I am a file, not a directory")
    s = make_settings(tmp_path)
    monkeypatch.setattr(install, "SETTINGS", s)
    monkeypatch.setattr(install, "HOOKS_DIR", file_not_dir)
    # Must return False cleanly — no exception
    assert install.is_hardgate_complete(verify) is False


# ── backup_configs() ──────────────────────────────────────────────────────────

def test_backup_configs_creates_timestamped_backup(tmp_path, monkeypatch):
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text('{"hooks": {}}')
    monkeypatch.setattr(install, "SETTINGS", settings)
    monkeypatch.setattr(install, "CC_CONFIG", tmp_path / ".claude.json")
    ts = install.backup_configs()
    backup = settings.parent / f"settings.json.stack-backup-{ts}"
    assert backup.exists()
    assert backup.read_text() == '{"hooks": {}}'


def test_backup_configs_returns_timestamp_string(tmp_path, monkeypatch):
    monkeypatch.setattr(install, "SETTINGS", tmp_path / "s.json")
    monkeypatch.setattr(install, "CC_CONFIG", tmp_path / "c.json")
    ts = install.backup_configs()
    assert len(ts) == 15  # YYYYMMDD-HHMMSS
    assert ts[8] == "-"


def test_backup_configs_handles_missing_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(install, "SETTINGS", tmp_path / "nonexistent.json")
    monkeypatch.setattr(install, "CC_CONFIG", tmp_path / "nonexistent.json")
    ts = install.backup_configs()
    assert isinstance(ts, str) and len(ts) > 0
    out = capsys.readouterr().out
    assert "not found" in out.lower() or "will be created" in out.lower()


# ── restore_configs() ─────────────────────────────────────────────────────────

def test_restore_configs_restores_from_backup(tmp_path, monkeypatch):
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    backup = settings.parent / "settings.json.stack-backup-20260101-120000"
    backup.write_text('{"original": true}')
    settings.write_text('{"original": false}')
    monkeypatch.setattr(install, "HOME", tmp_path)
    install.restore_configs("20260101-120000")
    assert json.loads(settings.read_text())["original"] is True


def test_restore_configs_warns_when_no_backup(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(install, "HOME", tmp_path)
    install.restore_configs("99991231-235959")
    out = capsys.readouterr().out
    assert "no backup" in out.lower() or "not present" in out.lower() or "not found" in out.lower()


# ── --verify flag ─────────────────────────────────────────────────────────────

def test_verify_flag_delegates_to_verifier_and_exits(monkeypatch):
    """python install.py --verify must call v.run() and sys.exit with its result."""
    monkeypatch.setattr(sys, "argv", ["install.py", "--verify"])
    mock_mod = MagicMock()
    mock_mod.run.return_value = 0
    with patch.object(install, "_load_verify", return_value=mock_mod):
        with pytest.raises(SystemExit) as exc_info:
            install.main()
    assert exc_info.value.code == 0
    mock_mod.run.assert_called_once()
