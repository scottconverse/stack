#!/usr/bin/env python3
"""
stack installer — standalone version

Installs Longhand, Context-Mode, and Hardgate (guided) without
requiring an open Claude Code session.

Usage:
  python install.py          # full install
  python install.py --verify # run post-install verification only
"""
from __future__ import annotations

__version__ = "1.1.2"

import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys
import datetime


# ── Terminal colour helpers ────────────────────────────────────────────────────
# Enable ANSI on Windows Terminal / Git Bash / VSCode; fall back to plain text
# on legacy cmd.exe where sequences would appear as raw characters.
_USE_ANSI = (
    sys.platform != "win32"
    or os.environ.get("WT_SESSION")      # Windows Terminal
    or os.environ.get("TERM")            # Git Bash / MSYS2
    or os.environ.get("TERM_PROGRAM")    # VSCode integrated terminal
)


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_ANSI else text


def green(t: str)  -> str: return _c("32", t)
def yellow(t: str) -> str: return _c("33", t)
def red(t: str)    -> str: return _c("31", t)
def bold(t: str)   -> str: return _c("1",  t)
def dim(t: str)    -> str: return _c("2",  t)


def _header(title: str) -> None:
    bar = "─" * 48
    print(f"\n{bold(bar)}")
    print(f"  {bold(title)}")
    print(bold(bar))


def _step(label: str) -> None:
    print(f"  {dim('→')} {label}")


def _ok(label: str) -> None:
    print(f"  {green('✓')} {label}")


def _warn(label: str) -> None:
    print(f"  {yellow('⚠')} {label}")


def _fail(label: str) -> None:
    print(f"  {red('✗')} {label}")


# ── Paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT  = pathlib.Path(__file__).parent.resolve()
VERIFY_PY  = REPO_ROOT / "scripts" / "verify.py"
HOME       = pathlib.Path.home()
SETTINGS   = HOME / ".claude" / "settings.json"
CC_CONFIG  = HOME / ".claude.json"
HOOKS_DIR  = HOME / ".claude" / "hooks"


# ── Load verify.py as a module ─────────────────────────────────────────────────
def _load_verify():
    if not VERIFY_PY.exists():
        print(red(f"\nCannot find {VERIFY_PY}"))
        print("This installer requires the full stack repo — do not copy install.py alone.")
        print("Clone: git clone https://github.com/scottconverse/stack")
        sys.exit(1)
    spec = importlib.util.spec_from_file_location("verify", VERIFY_PY)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Run a command quietly; dump captured output only on failure ────────────────
def _run(cmd: list[str], cwd: str | pathlib.Path | None = None) -> int:
    try:
        result = subprocess.run(
            cmd, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError:
        print()
        _fail(f"command not found: {cmd[0]}")
        return 127  # standard shell exit code for "command not found"
    if result.returncode != 0 and result.stdout.strip():
        print()
        print(dim("  " + "─" * 46))
        for line in result.stdout.rstrip().splitlines():
            print(f"  {line}")
        print(dim("  " + "─" * 46))
    return result.returncode


# ── Prerequisite checks ────────────────────────────────────────────────────────
def check_prereqs() -> list[str]:
    """
    Check Python, Node.js, and Claude Code.
    - Node.js missing: print platform-specific install command.
    - Claude Code missing: offer to install via npm.
    Returns a list of failure strings for anything that could not be resolved.
    """
    failures = []

    # Python 3.10+ (already running, but guard against marginal cases)
    if sys.version_info < (3, 10):
        failures.append(
            f"Python 3.10+ required (found {sys.version.split()[0]})\n"
            "    Download: https://python.org/downloads"
        )
    else:
        _ok(f"Python {sys.version.split()[0]}")

    # Node.js 18+
    node = shutil.which("node")
    if not node:
        if sys.platform == "win32":
            hint = "winget install OpenJS.NodeJS"
        elif sys.platform == "darwin":
            hint = "brew install node"
        else:
            hint = "sudo apt install nodejs   # or use nvm: https://github.com/nvm-sh/nvm"
        failures.append(
            f"Node.js 18+ not found\n"
            f"    Install: {hint}\n"
            "    Then re-run install.py"
        )
        # Can't check npm / claude without node — return early
        return failures
    else:
        try:
            out = subprocess.check_output(
                [node, "--version"], text=True, stderr=subprocess.DEVNULL
            ).strip()
            major = int(out.lstrip("v").split(".")[0])
            if major < 18:
                failures.append(
                    f"Node.js 18+ required (found {out})\n"
                    "    Download: https://nodejs.org"
                )
                return failures
            else:
                _ok(f"Node.js {out}")
        except (ValueError, subprocess.SubprocessError):
            failures.append("Could not determine Node.js version — https://nodejs.org")
            return failures

    # Claude Code CLI — offer to install if missing
    if not shutil.which("claude"):
        _warn("Claude Code CLI not found")
        try:
            reply = input("  Install it now via npm? [Y/n]: ").strip().lower()
        except KeyboardInterrupt:
            print()
            reply = "n"
        if reply in ("", "y", "yes"):
            npm = shutil.which("npm")
            if not npm:
                failures.append(
                    "npm not found — Node.js should include it\n"
                    "    Try reinstalling Node.js: https://nodejs.org"
                )
            else:
                _step("npm install -g @anthropic-ai/claude-code")
                code = _run([npm, "install", "-g", "@anthropic-ai/claude-code"])
                if code != 0:
                    failures.append(
                        "Claude Code install failed — see output above\n"
                        "    Install manually: https://claude.ai/code"
                    )
                else:
                    _ok("Claude Code CLI installed")
        else:
            failures.append(
                "Claude Code CLI required\n"
                "    Install: npm install -g @anthropic-ai/claude-code\n"
                "    Or visit: https://claude.ai/code"
            )
    else:
        _ok("Claude Code CLI")

    return failures


# ── Config backup ──────────────────────────────────────────────────────────────
def backup_configs() -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    for src in [SETTINGS, CC_CONFIG]:
        if src.exists():
            dst = src.parent / f"{src.name}.stack-backup-{ts}"
            shutil.copy2(src, dst)
            _ok(f"backed up  {src.name}  →  {dst.name}")
        else:
            _warn(f"{src.name} not found — will be created by installers")
    return ts


# ── Idempotency checks ─────────────────────────────────────────────────────────
def is_longhand_complete(v) -> bool:
    return all([
        shutil.which("longhand") is not None,
        v.check_longhand_session_end(SETTINGS)["ok"],
        v.check_longhand_prompt_hook(SETTINGS)["ok"],
        v.check_longhand_mcp(SETTINGS, CC_CONFIG)["ok"],
    ])


def is_context_mode_complete(v) -> bool:
    return all([
        v.check_context_mode_hooks(SETTINGS)["ok"],
        v.check_context_mode_mcp(SETTINGS, CC_CONFIG)["ok"],
    ])


def is_hardgate_complete(v) -> bool:
    try:
        return v.check_hardgate_artifacts(SETTINGS, HOOKS_DIR)["ok"]
    except Exception:
        # Catch broadly: malformed hook data, NotADirectoryError if HOOKS_DIR
        # is a file, OSError on permission errors, TypeError on unexpected
        # structure — all mean "not fully installed."
        return False


# Directories at home-directory depth-1 that will never contain Context-Mode.
# Skipping these makes the bounded walk significantly faster on developer machines.
_SKIP_DIRS = frozenset({
    ".cargo", ".npm", ".gradle", ".cache", ".local", ".config",
    ".git", ".svn", ".hg", ".idea", ".vscode", ".eclipse",
    "node_modules", "Library", "AppData", "System", "Windows",
    ".android", ".dotnet", ".nuget", ".m2",
    "__pycache__", ".pyenv", ".rbenv", ".nvm", ".rustup",
    ".ssh", ".gnupg", ".kube", ".terraform", ".aws",
})


def _is_context_mode_install_js(path: pathlib.Path) -> bool:
    """Return True only if install.js looks like the real Context-Mode installer.

    Checking content prevents false positives from unrelated projects
    that happen to be named context-mode or contain an install.js.
    """
    try:
        text = path.read_text(errors="ignore")
        return "context-mode" in text or "context_mode" in text
    except OSError:
        return False


# ── Context-Mode discovery ─────────────────────────────────────────────────────
def _find_context_mode_dir() -> pathlib.Path | None:
    # 1. Plugin cache — highest confidence, check first
    cache = HOME / ".claude" / "plugins" / "cache"
    if cache.exists():
        for p in cache.rglob("install.js"):
            if ("context-mode" in str(p) or "context_mode" in str(p)) \
                    and _is_context_mode_install_js(p):
                return p.parent

    # 2. Bounded Python-native walk (cross-platform — no 'find' dependency).
    # Skips common system/tool directories that will never contain Context-Mode.
    for depth1 in HOME.iterdir():
        try:
            if not depth1.is_dir() or depth1.name in _SKIP_DIRS:
                continue
            for depth2 in depth1.iterdir():
                try:
                    if not depth2.is_dir():
                        continue
                    candidate = depth2 / "install.js"
                    if candidate.exists() and (
                        "context-mode" in depth2.name
                        or "context_mode" in depth2.name
                    ) and _is_context_mode_install_js(candidate):
                        return depth2
                    # depth 3
                    for depth3 in depth2.iterdir():
                        try:
                            if not depth3.is_dir():
                                continue
                            candidate = depth3 / "install.js"
                            if candidate.exists() and (
                                "context-mode" in depth3.name
                                or "context_mode" in depth3.name
                            ) and _is_context_mode_install_js(candidate):
                                return depth3
                        except PermissionError:
                            continue
                except PermissionError:
                    continue
        except PermissionError:
            continue

    return None


# ── Installers ────────────────────────────────────────────────────────────────
def install_longhand() -> bool:
    _header("Longhand  (memory layer)")

    steps = [
        ([sys.executable, "-m", "pip", "install", "longhand"],
         "pip install longhand"),
        (["longhand", "setup"],
         "longhand setup"),
        (["longhand", "prompt-hook", "install"],
         "longhand prompt-hook install"),
        (["claude", "mcp", "add", "longhand", "-s", "user",
          "--", "longhand", "mcp-server"],
         "claude mcp add longhand"),
    ]

    for cmd, label in steps:
        _step(label)
        code = _run(cmd)
        if code != 0:
            _fail(f"{label} failed (exit {code})")
            print(red("\n  Aborting. Fix the error above and re-run install.py"))
            return False
    _ok("Longhand installed")
    return True


def install_context_mode(ctx_dir: pathlib.Path) -> bool:
    _header("Context-Mode  (context layer)")
    print(f"  {dim('using')} {ctx_dir}")
    _step("node install.js")
    code = _run(["node", "install.js"], cwd=str(ctx_dir))
    if code != 0:
        _fail("node install.js failed — see output above")
        return False
    _ok("Context-Mode installed")
    return True


def install_hardgate() -> None:
    _header("Hardgate  (enforcement layer)")
    print(f"""
  {yellow('Hardgate cannot be fully automated.')} It requires the /hard-gate
  skill inside an active Claude Code session.

  {bold('Steps:')}
    1. Open a new terminal and start Claude Code:  {bold('claude')}
    2. Type:  {bold('/hard-gate')}
    3. Follow the prompts to choose which tools to enforce
    4. Wait for it to complete
    5. Come back here and press Enter

""")
    try:
        input("  Press Enter when Hardgate is done  (Ctrl+C to skip)... ")
        _ok("Continuing to verification")
    except KeyboardInterrupt:
        print()
        _warn("Hardgate skipped — run /hard-gate in Claude Code when ready")


# ── Restore configs on exit 2 ─────────────────────────────────────────────────
def restore_configs(ts: str) -> None:
    _header("Restoring config backups")
    for src_name, base in [("settings.json", HOME / ".claude"), (".claude.json", HOME)]:
        backup = base / f"{src_name}.stack-backup-{ts}"
        dest   = base / src_name
        if backup.exists():
            shutil.copy2(backup, dest)
            _ok(f"Restored {src_name}")
        else:
            _warn(f"No backup found for {src_name} (was not present before install)")


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    # Verify-only mode
    if "--verify" in sys.argv:
        v = _load_verify()
        sys.exit(v.run())

    # Banner
    print(f"\n{bold('Stack Installer')}  {dim(f'v{__version__}')}")
    print(dim("github.com/scottconverse/stack"))
    print(dim("Installs Longhand · Context-Mode · Hardgate\n"))

    v = _load_verify()

    # Prerequisites
    _header("Prerequisites")
    failures = check_prereqs()
    if failures:
        for f in failures:
            _fail(f)
        print(red("\n  Fix the issues above, then re-run install.py"))
        sys.exit(1)

    # Context-Mode discovery — done here so the user sees all "missing piece"
    # prompts before installation starts, not mid-flow as a surprise.
    ctx_dir = _find_context_mode_dir()
    if ctx_dir is None:
        print()
        _warn("Context-Mode not found in plugin cache or home directory")
        try:
            reply = input("  Clone scottconverse/context-mode now? [Y/n]: ").strip().lower()
        except KeyboardInterrupt:
            print()
            reply = "n"
        if reply in ("", "y", "yes"):
            clone_target = HOME / ".claude" / "plugins" / "context-mode"
            _step(f"git clone → {clone_target}")
            code = _run([
                "git", "clone",
                "https://github.com/scottconverse/context-mode",
                str(clone_target),
            ])
            if code != 0:
                _fail("Clone failed — install context-mode manually and re-run")
                sys.exit(1)
            ctx_dir = clone_target
            _ok(f"Context-Mode cloned")
        else:
            _fail("Context-Mode required — clone manually and re-run")
            sys.exit(1)
    else:
        _ok(f"Context-Mode found")

    # Backup
    _header("Config backup")
    ts = backup_configs()

    # Longhand
    if is_longhand_complete(v):
        _header("Longhand  (memory layer)")
        _ok("Fully installed — skipping")
    else:
        if not install_longhand():
            sys.exit(1)

    # Context-Mode
    if is_context_mode_complete(v):
        _header("Context-Mode  (context layer)")
        _ok("Fully installed — skipping")
    else:
        if not install_context_mode(ctx_dir):
            sys.exit(1)

    # Hardgate
    if is_hardgate_complete(v):
        _header("Hardgate  (enforcement layer)")
        _ok("Fully installed — skipping")
    else:
        install_hardgate()

    # Verification
    _header("Verification")
    exit_code = v.run()

    if exit_code == 2:
        restore_configs(ts)
        print(red("\n  Both config files restored to pre-install state."))
        print("  Retry each failed step manually using the commands above.")

    elif exit_code == 0:
        print(f"\n  {green('All checks passed.')} Restart Claude Code to activate the stack.")
        print(f"  Then run:  {bold('longhand doctor')}  and  {bold('claude mcp list')}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
