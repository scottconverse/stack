# Stack Installer

**Shell requirement:** bash-compatible shell only. Git Bash or WSL on Windows.
Not PowerShell. Not cmd.exe.

Install Longhand, Context-Mode, and Hardgate as a coordinated Claude Code
stack. Follow every phase in order. Do not skip any step.

---

## Phase 0 — Locate verify.py

Find the verifier before doing anything else. Try in order:

**Option 1: env var**
```bash
[ -n "$STACK_DIR" ] && [ -f "$STACK_DIR/scripts/verify.py" ] \
  && echo "VERIFY_PY=$STACK_DIR/scripts/verify.py" \
  || echo "not in STACK_DIR"
```

**Option 2: plugin cache**
```bash
find ~/.claude/plugins -name "verify.py" -path "*/stack/scripts/*" 2>/dev/null | head -1
```

**Option 3: bounded home search (slower)**
```bash
find "$HOME" -maxdepth 4 -name "verify.py" -path "*/stack/scripts/*" 2>/dev/null | head -1
```

Store the result as VERIFY_PY. If all three find nothing, tell the user:

> "verify.py not found. This skill requires the full stack repo to be
> present — cloning just the skill file is not supported.
> Run: git clone https://github.com/scottconverse/stack
> Then set STACK_DIR to the cloned path and re-run /stack."

**STOP if VERIFY_PY is not set.**

---

## Phase 1 — Pre-flight

### Step 1.1: Check prerequisites

Run each check. Collect all failures before stopping — report them all
at once, not one at a time.

**Python 3.10+:**
```bash
python --version
```
If missing or below 3.10: https://python.org/downloads

**Node.js 18+:**
```bash
node --version
```
If missing or below 18: https://nodejs.org

**Context-Mode location:**
```bash
find ~/.claude/plugins/cache -maxdepth 3 -name "install.js" -path "*context*" 2>/dev/null | head -3
```
If not found, ask: "Where is your context-mode directory? Provide the
full path to the directory containing install.js."

Store as CTX_DIR.

If any prerequisite is missing: list all failures with fix instructions.
**Stop.** Do not proceed until all are met.

### Step 1.2: Timestamped backup of both config files

```bash
STACK_TS=$(date +%Y%m%d-%H%M%S)

cp ~/.claude/settings.json \
   ~/.claude/settings.json.stack-backup-$STACK_TS 2>/dev/null \
  && echo "settings.json backed up (stack-backup-$STACK_TS)" \
  || echo "settings.json not found — will be created by installers"

cp ~/.claude.json \
   ~/.claude.json.stack-backup-$STACK_TS 2>/dev/null \
  && echo ".claude.json backed up (stack-backup-$STACK_TS)" \
  || echo ".claude.json not found — will be created by installers"
```

Remember STACK_TS — it is used in the restore step if needed.

### Step 1.3: Full idempotency check per tool

Run this Python snippet to check which tools are fully installed:

```bash
python - <<'EOF'
import json, shutil, pathlib

home = pathlib.Path.home()
settings_path = home / ".claude" / "settings.json"
cc_path = home / ".claude.json"

try:
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
except Exception:
    settings = {}
try:
    cc = json.loads(cc_path.read_text()) if cc_path.exists() else {}
except Exception:
    cc = {}

hooks = settings.get("hooks", {})

def contains(entries, needle):
    for e in entries:
        cmd = ""
        inner = e.get("hooks") if isinstance(e, dict) else None
        if isinstance(inner, list):
            cmd = " ".join(h.get("command","") for h in inner if isinstance(h,dict))
        else:
            cmd = e.get("command","") if isinstance(e,dict) else ""
        if needle in cmd:
            return True
    return False

longhand_ok = all([
    shutil.which("longhand") is not None,
    contains(hooks.get("SessionEnd",[]), "longhand ingest-session"),
    contains(hooks.get("UserPromptSubmit",[]), "__prompt-hook-run"),
    "longhand" in settings.get("mcpServers",{}) or "longhand" in cc.get("mcpServers",{}),
])

REQUIRED_MATCHERS = {"Bash", "Read", "WebFetch"}
ctx_hooks = [e for e in hooks.get("PreToolUse",[])
             if "context-mode" in str(e)]
matchers = [e.get("matcher","") for e in ctx_hooks if isinstance(e,dict)]
named = [m for m in matchers if m]
ctx_ok = all([
    len(ctx_hooks) >= 3,
    REQUIRED_MATCHERS.issubset(set(named)),
    len(named) == len(set(named)),
    "context-mode" in settings.get("mcpServers",{}) or "context-mode" in cc.get("mcpServers",{}),
])

print(f"longhand_fully_installed={'yes' if longhand_ok else 'no'}")
print(f"context_mode_fully_installed={'yes' if ctx_ok else 'no'}")
EOF
```

Report which tools are already fully installed. Skip their install
steps in Phase 2. If a tool is partially installed (some but not all
artifacts present), do NOT skip — re-run its installer to complete it.

---

## Phase 2 — Install

### Step 2.1: Longhand (skip only if longhand_fully_installed=yes)

If skipping: print "Longhand fully installed — skipping." Go to Step 2.2.

Otherwise run each command. **Wait for completion before the next.**

```bash
pip install longhand
```
Expected: `Successfully installed longhand-...`
If it outputs "already satisfied," that is fine — continue.

```bash
longhand setup
```
Expected: Reports sessions ingested and hooks wired. This command is
typically non-interactive but may prompt for confirmation on first run —
answer yes to all prompts. Allow up to 90 seconds for initial history
ingest.

```bash
longhand prompt-hook install
```
Expected: `✓ Installed UserPromptSubmit hook`

```bash
claude mcp add longhand -s user -- longhand mcp-server
```
Expected: MCP server registered.

If any command fails: report the error and exact retry command.
**Do NOT continue to Step 2.2 until all four succeed.**

### Step 2.2: Context-Mode (skip only if context_mode_fully_installed=yes)

If skipping: print "Context-Mode fully installed — skipping." Go to Step 2.3.

Otherwise run from CTX_DIR:
```bash
node install.js
```
Expected: All install steps pass.

If it fails: report the exact error. **Do NOT continue to Step 2.3.**

### Step 2.3: Hardgate (interactive — hard pause)

Before pausing, persist the session variables to a temp file so they
survive the interaction boundary:

```bash
cat > ~/.claude/stack-session.env <<EOF
VERIFY_PY=$VERIFY_PY
STACK_TS=$STACK_TS
CTX_DIR=$CTX_DIR
EOF
echo "Session state saved to ~/.claude/stack-session.env"
```

Then tell the user:

> Longhand and Context-Mode are installed. Hardgate requires one
> decision from you.
>
> Run `/hard-gate` now and follow the prompts to choose which tools
> to enforce. When it is done, reply to this message and I will run
> the final verification.

**STOP. Do not run verify.py or print results until the user replies.
This is not optional.**

---

## Phase 3 — Post-Verify

### Step 3.1: Restore session variables

```bash
source ~/.claude/stack-session.env
echo "VERIFY_PY=$VERIFY_PY  STACK_TS=$STACK_TS"
```

If either is empty, ask the user: "Where did you clone the stack repo?
I need the path to scripts/verify.py and the backup timestamp to proceed."

### Step 3.2: Run the verifier

```bash
python "$VERIFY_PY"
VERIFY_EXIT=$?
```

### Step 3.3: Interpret and act

**Exit 0 — all required checks pass:**
Print the verifier output. Tell the user to restart Claude Code.

**Exit 1 — one or more required checks failed, settings.json is valid:**
Print the verifier output. Do NOT restore from backup — successful
installs remain in place. The failed checks show exact retry commands.

**Exit 2 — a config file exists but is malformed:**
Restore both timestamped backups:

```bash
cp ~/.claude/settings.json.stack-backup-$STACK_TS ~/.claude/settings.json \
  && echo "settings.json restored"

cp ~/.claude.json.stack-backup-$STACK_TS ~/.claude.json 2>/dev/null \
  && echo ".claude.json restored" \
  || echo ".claude.json backup not present (was not installed pre-stack)"
```

Report: "Both config files restored to their pre-install state. Retry
each failed step manually:" — then list the retry commands for every
install step.
