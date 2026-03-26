# Workflow: Onboarding Dependencies

## Objective
Make sure the local machine has the runtime prerequisites needed for this project before any setup that
depends on them.

## When This Runs
- Only read this file if onboarding is incomplete.
- Skip any check that has already passed in the current run.

## Prerequisites Covered

### Indeed
- Connect at `claude.ai -> Settings -> Integrations -> Indeed`
- Carries over to Claude Code automatically
- If missing, reconnect at claude.ai and restart Claude Code

### Python
Tell the user:
`First I'm going to make sure everything needed to run this system is installed. I'll check each thing before doing anything - if it's already there, I'll skip it.`

Tell the user:
`Checking for Python...`

Run these checks in order and stop as soon as one succeeds:
1. `py --version 2>&1`
2. `python --version 2>&1`
3. `python3 --version 2>&1`

A check succeeds if the output contains `Python 3.`

A check fails if the output contains `Microsoft Store`, `was not found`, `not recognized`, or errors out.

- If any check succeeds: tell the user Python is already installed and keep using that same command name.
- If all three fail:
  - Windows: run `winget install Python.Python.3`, then verify with `py --version`
  - macOS: run `brew install python`, then verify with `python3 --version`
  - Other: tell the user to install Python from `https://python.org`, wait for `done`, then verify

If Python is still missing after install, stop and show the error.

### Python Packages
Tell the user:
`Installing required Python packages...`

Run `pip install -r requirements.txt` from the project root.

- If `pip` is not found, try `pip3 install -r requirements.txt`
- If installation still fails, show the error and stop

### Indeed MCP
Verify `mcp__claude_ai_Indeed__search_jobs` is accessible.

- If available: continue
- If not available: tell the user
  `Indeed isn't connected. Go to claude.ai -> Settings -> Integrations, connect Indeed, then restart Claude Code and run again.`
  Then stop
