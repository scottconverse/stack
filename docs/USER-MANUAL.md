# Stack — User Manual

**Plain-language guide to what this does, how to use it, and what to do when something goes wrong.**

---

## What is this?

`stack` installs three tools that work together to make Claude Code more reliable, more self-aware, and more controlled. A standalone installer (`install.py`) and a Claude Code skill (`/stack`) both set up all three tools in the right order with the right wiring — choose the path that fits your situation.

Once installed, these tools run automatically in the background every time you use Claude Code. You do not need to think about them during normal use. They change *how* Claude behaves, not what you ask it to do.

---

## The three tools, in plain language

### Longhand — Claude's memory

By default, Claude Code forgets everything when you close a session. Longhand fixes this. It saves every conversation to a database on your computer and gives Claude a way to search those past sessions. When you start a new conversation, Claude can recall what you worked on before — decisions made, bugs found, files changed.

**What you'll notice:** Claude will sometimes reference previous conversations without you prompting it. You can also ask Claude directly: "What did we work on last week?" and it will know.

**What it stores:** Conversation text, on your own computer. Nothing is sent to the cloud. The database lives in your home directory.

### Context-Mode — Keeps Claude's working memory clean

When Claude runs a command — like reading a file, running a test, or fetching a web page — the raw output of that command normally flows directly into the conversation and takes up space. On large codebases or long sessions, this causes Claude to start forgetting earlier parts of the conversation.

Context-Mode intercepts those command outputs and processes them in a sandbox. Claude gets a summary of what it needs rather than the full raw dump. The conversation stays focused.

**What you'll notice:** Claude Code sessions run longer before hitting context limits. Claude is less likely to forget things from earlier in a long session.

**What it does not do:** It does not change Claude's answers. It does not hide information from Claude. It filters noise, not content.

### Hardgate — Enforces rules

Hardgate lets you define tools that Claude is not allowed to use without your explicit approval. For example, you can block Claude from pushing to GitHub, deleting files, or running database migrations without pausing to ask you first.

When Hardgate is active and Claude tries to use a blocked tool, it stops and tells you. You decide whether to proceed.

**What you'll notice:** Before certain risky operations, Claude will stop and ask rather than act. This is intentional.

**What it does not block by default:** Everything. Hardgate has no blocked tools until you configure it. The `/stack` installer sets up the infrastructure; you choose the rules.

---

## How they work together

```
Your request
     │
     ▼
 Hardgate ──── Is this tool on the blocked list?
     │              YES → Stop. Ask the user.
     │              NO  → Continue.
     ▼
Context-Mode ── Run the tool in a sandbox.
     │              Feed Claude a clean summary, not raw output.
     ▼
  Longhand ──── At session end, save everything to memory.
                At session start, make past sessions searchable.
```

Each layer is independent. If one is misconfigured, the others still work. They do not depend on each other at runtime — they each modify a different part of how Claude Code processes requests.

### Architecture: what hooks each tool uses

Claude Code has a hook system — commands that run automatically at specific moments. Each tool in the stack uses a different hook, so they never conflict.

```
EVENT                   TOOL            WHAT HAPPENS
─────────────────────────────────────────────────────────────────────
UserPromptSubmit        Longhand        Records your message to local DB
  (every message)

PreToolUse              Hardgate        Checks the tool against blocked list
  (before every         Context-Mode    Intercepts output; sends to sandbox
   tool call)

SessionEnd              Longhand        Ingests full session into memory
  (on close)
```

**Where the config lives:**
All three tools write their hook entries into `~/.claude/settings.json`. The MCP servers (Longhand's memory query endpoint and Context-Mode's sandbox) are registered in `mcpServers` in the same file. The `/stack` installer writes all of this for you; `verify.py` confirms it afterwards.

```
~/.claude/settings.json
├── hooks
│   ├── UserPromptSubmit   ← Longhand prompt hook
│   ├── PreToolUse         ← Hardgate (exit 2) + Context-Mode (3+ matchers)
│   └── SessionEnd         ← Longhand ingest
└── mcpServers
    ├── longhand           ← Longhand memory server
    └── context-mode       ← Context-Mode sandbox server
```

### Architecture: the request flow in detail

Here is what happens from the moment you send a message to Claude through to the end of the session:

```
1. You type a message
        │
        ▼
2. UserPromptSubmit fires
   └─ Longhand records the prompt to its database

3. Claude decides to use a tool (e.g. run a bash command)
        │
        ▼
4. PreToolUse fires — Hardgate checks first
   ├─ Tool is on the blocked list?
   │   YES → exit 2. Claude stops. Tells you. Waits.
   │   NO  → continues to step 5
        │
        ▼
5. PreToolUse fires — Context-Mode intercepts
   └─ Runs the tool in a sandboxed subprocess
      Summarises the output
      Feeds Claude the summary, not the raw dump

6. Claude uses the summary to form its response

7. You close the session
        │
        ▼
8. SessionEnd fires
   └─ Longhand ingests the full conversation
      Makes it searchable in future sessions
```

---

## Installation walkthrough

### Before you start

You need:
- **Python 3.10 or newer** — check by running `python --version` in your terminal
- **Node.js 18 or newer** — check by running `node --version` in your terminal
- **Claude Code** installed (the command-line tool from Anthropic)
- **The stack repo cloned to your computer** — see below

**On Windows:** Any terminal works for Option A (the standalone installer) — Command Prompt, PowerShell, or Git Bash. Option B (the Claude Code skill) requires a bash-compatible terminal: Git Bash or WSL.

### Step 1: Clone the repo

```bash
git clone https://github.com/scottconverse/stack
cd stack
```

This downloads everything the installer needs. Do not copy just the skill file — the installer requires the full repo.

### Step 2: Choose your install path

**Option A — Standalone installer (no Claude Code session needed):**

```bash
# macOS / Linux
bash install.sh

# Windows — double-click install.bat, or from any terminal:
python install.py
```

The installer runs in your terminal, checks prerequisites, installs everything automatically, and pauses once to ask which tools Hardgate should enforce. When it finishes, it prints a verification summary. If everything is green, proceed to Step 3.

**Option B — Claude Code skill (from inside an active session):**

Start Claude Code, then type `/stack` and press Enter.

```bash
claude
# then type: /stack
```

Claude guides you through the same steps interactively. There is one pause — Hardgate — where you choose which tools to enforce.

### Step 3: Restart Claude Code

When the installer reports verification passed, close and reopen Claude Code. The new tools take effect on the next session.

### Step 4: Verify runtime health

After restarting, confirm everything is running:

```bash
longhand doctor
claude mcp list
```

`longhand doctor` should show a green status for its database and MCP server. `claude mcp list` should show `longhand` and `context-mode` in the list.

---

## Running the installer again (idempotency)

Both install paths are safe to run repeatedly.

- **Standalone:** `python install.py` — checks which tools are already fully installed and skips them.
- **Skill:** `/stack` — does the same check before each step.

Neither path creates duplicate entries or overwrites a working install. If a tool is partially installed, re-running will complete it.

---

## What the verifier checks

After installation, `scripts/verify.py` runs automatically and checks:

| Check | What it means if it fails |
|-------|--------------------------|
| Longhand SessionEnd hook | Longhand is not saving sessions. Run `longhand setup`. |
| Longhand UserPromptSubmit hook | Longhand's prompt hook is not active. Run `longhand prompt-hook install`. |
| Context-Mode PreToolUse hooks | Context-Mode is not intercepting tool calls. Run `node install.js` from your context-mode directory. |
| Longhand MCP server | Claude cannot query Longhand's memory. Run `claude mcp add longhand -s user -- longhand mcp-server`. |
| Context-Mode MCP server | Claude cannot use the Context-Mode sandbox. Run `node install.js` from your context-mode directory. |
| Hardgate enforcement | Hardgate is installed but no enforcement target is set. Run `/hard-gate` and follow the prompts to choose which tools to enforce. |

The verifier will print the exact retry command for each failure. Follow those commands in order.

---

## What to do when things go wrong

### `install.py` says Python is not found or is below 3.10

The installer checks your Python version before starting. If it reports Python is missing or too old:

- **Windows:** Download from [python.org/downloads](https://python.org/downloads). During install, check "Add Python to PATH."
- **macOS:** Run `brew install python` (requires Homebrew), or download from python.org.
- **Linux:** Run `sudo apt install python3` or the equivalent for your distribution.

After installing, open a new terminal window and run `python --version` to confirm the version, then retry.

### `install.py` fails partway through

The installer saves a timestamped backup of your Claude config before it starts. If something goes wrong mid-install, your original settings are not lost.

Re-run `python install.py`. The installer checks which steps succeeded and skips them — it will only retry what failed.

If the problem persists, look at the error message. The installer prints the exact command that failed and a suggested fix. Run that command manually, then re-run `python install.py` to continue.

### "verify.py not found"

You copied just the skill file instead of cloning the full repo. Clone the full repo:

```bash
git clone https://github.com/scottconverse/stack
```

Then set `STACK_DIR` to the cloned path and run `/stack` again:

```bash
export STACK_DIR=/path/to/stack
```

### The verifier exits with code 2

This means one of your Claude config files is malformed (corrupted JSON). The installer automatically restores your pre-install backup. Your settings are returned to exactly the state they were in before you ran `/stack`.

After the restore, retry each failed step manually using the commands the verifier printed.

### "longhand doctor" shows a failure

Longhand's MCP server is registered in your config but not responding. Try:

```bash
longhand setup
```

If that does not fix it, check that Python 3.10+ is still on your PATH:

```bash
python --version
```

### "claude mcp list" does not show longhand or context-mode

The MCP server entries are missing from your config. Re-run the relevant install step:

For Longhand:
```bash
claude mcp add longhand -s user -- longhand mcp-server
```

For Context-Mode:
```bash
node install.js
```
(Run this from the directory where you cloned context-mode.)

### Claude is not recalling past sessions

Longhand may be installed but has no ingested history yet. Run:

```bash
longhand ingest-session
```

Then start a new Claude Code session.

### A tool was only partially installed

Re-run whichever path you used:
- **Standalone:** `python install.py`
- **Skill:** `/stack`

Both installers detect partial installs and re-run only the steps that are incomplete.

---

## Restoring your original config manually

Each time you run `/stack`, it saves a timestamped backup of your config files:

```
~/.claude/settings.json.stack-backup-YYYYMMDD-HHMMSS
~/.claude.json.stack-backup-YYYYMMDD-HHMMSS
```

To find your most recent backup:

```bash
ls -t ~/.claude/settings.json.stack-backup-* | head -1
```

To restore it:

```bash
cp ~/.claude/settings.json.stack-backup-YYYYMMDD-HHMMSS ~/.claude/settings.json
```

Replace `YYYYMMDD-HHMMSS` with the timestamp from the `ls` output.

---

## Glossary

**Claude Code** — Anthropic's command-line interface for Claude. It runs in your terminal and lets you give Claude tasks that involve your local files, code, and development tools.

**MCP server** — A background process that Claude Code can connect to and query. Longhand and Context-Mode each run as MCP servers so Claude can call them during a session.

**Hook** — A command that Claude Code runs automatically at certain points: before a tool runs, after a session ends, when you submit a prompt. Hooks are how Longhand, Context-Mode, and Hardgate connect into Claude Code's workflow.

**settings.json** — Claude Code's main configuration file, stored at `~/.claude/settings.json`. Hooks, MCP server registrations, and other settings live here.

**SessionEnd hook** — A hook that runs when you close a Claude Code session. Longhand uses this to save the session to its database.

**PreToolUse hook** — A hook that runs before Claude uses a tool (like running a bash command or reading a file). Context-Mode and Hardgate both use this.

**UserPromptSubmit hook** — A hook that runs every time you send a message to Claude. Longhand uses this to track prompts.

**Context window** — The amount of text Claude can hold in its active memory at one time. When the context window fills up, Claude starts to lose track of earlier parts of the conversation. Context-Mode helps delay this.

**Idempotent** — Safe to run multiple times with the same result. Both `python install.py` and `/stack` are idempotent: running either twice does not double-install anything.

**Exit code** — A number a program returns when it finishes. Exit 0 means success. Exit 1 means something failed. Exit 2 means a config file is corrupted.
