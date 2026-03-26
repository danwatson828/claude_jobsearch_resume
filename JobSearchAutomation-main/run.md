# run.md — Entry Point

This file is read by Claude every time the workflow starts — whether you triggered it manually
or the scheduled task fired automatically.

---

## What This Workflow Does (Plain English)

This system does three things automatically:

1. **Searches Indeed** for jobs that match your saved criteria (titles, location, salary, keywords)
2. **Adds new jobs** to a Google Sheet so you have a running tracker — no duplicates, ever
3. **Rewrites your resume** for each new job to mirror that job's language and keywords,
   then saves each version as a Google Doc

The first time you run it, there's a one-time setup (~5 minutes). After that, everything
runs on a schedule with no input from you.

On the very first successful setup run, onboarding should end after setup and scheduling.
Do not automatically run a job search unless the user explicitly asks for an initial run.

---

## Execution Order

### Step 1: Onboarding

Claude reads and follows `workflows/onboarding.md`.

**What the user sees:** Plain English prompts asking for your job criteria, schedule preference,
and Google sign-in. Each step explains what it's doing and why before it does anything.

**What happens under the hood:**
- Checks that Python and the required Python packages are installed
  (installs anything missing automatically, with your confirmation)
- Walks you through Google authentication once — opens a browser, you sign in, done
- Asks for your job search preferences one question at a time
- Creates your Google Sheet tracker
- Uploads your resume to Google Drive
- Reminds you to use Claude Code in VS Code or the Claude Code CLI, and to use your OS scheduler for automatic recurring runs if desired

**If already set up:** Onboarding detects that `.env` is complete and skips itself entirely.
The whole check takes under a second, and the workflow continues normally.

### Step 1.5: Post-Onboarding Stop

If onboarding ran because setup fields were missing, stop here after onboarding completes.

Tell the user:
`You're all set. Next, run this project from Claude Code in VS Code or from the Claude Code CLI in this folder. If you want automatic recurring runs, I can help set that up now using the /loop slash command. Examples: /loop 5m check the deploy, /loop 30m /babysit-prs, /loop 1h run the workflow. If you would like, I can also perform an initial job search now.`

Only continue to Step 2 if the user explicitly says yes.

### Step 2: Job Search

Claude reads and follows `workflows/search_jobs.md`.

**What the user sees:** Nothing — this runs silently.

**What happens under the hood:**
- Reads your saved criteria from `.env`
- Searches Indeed for matching jobs
- Filters out anything already in your sheet
- Adds new jobs to the sheet with status "New"
- Rewrites your resume for each new job and saves it as a Google Doc
- Writes the resume link into the Notes column for that job row

---

## What Claude Will Tell You Along the Way

Claude narrates each major action in plain English before doing it. For example:
- *"Checking if Python is installed..."*
- *"I found your resume — is this the right file?"*
- *"Creating your Job Tracker sheet in Google Drive..."*
- *"Found 4 new jobs. Adding them to your sheet and tailoring your resume for each one..."*

You will never see a wall of code or a silent hang. If something takes more than a few seconds,
Claude will say what it's waiting for.

### About Permission Prompts

You may occasionally see a box asking you to approve a command. This is Claude Code asking
for your permission before it does anything on your computer — it cannot act without your say-so.

Before every permission prompt, Claude will explain in plain English what it's about to do and why,
so you're never approving something you don't understand. For example:

> *"I'm going to save your job title preference to a file on your computer. You'll see a permission
> prompt — go ahead and approve it."*

If you ever see a prompt and aren't sure what it's for, just ask: "What is this doing?" before approving.

---

## Connections Used

| Service | How It Connects |
|---|---|
| **Indeed** | Via your claude.ai account (connect once at claude.ai → Settings → Integrations) |
| **Google** (Drive, Docs, Sheets) | Via the Python tools in this project using your own Google Cloud project and OAuth setup (free, ~5 min setup) |

---

## Security

Nothing sensitive is stored in this project folder.
- `.env` holds your job preferences and sheet/drive URLs — nothing secret
- Google credentials live encrypted on your machine only (`~/.config/gws/`)
- Indeed auth is handled entirely by claude.ai

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Want to change job criteria | Delete the relevant lines from `.env`, then run again |
| No jobs found | Check `LOCATION` and `JOB_TITLES` in `.env` |
| Google tools not responding | Run `python tools/google_auth.py` in a terminal, then restart Claude Code |
| Sheet not updating | Verify `GOOGLE_SHEET_ID` in `.env` |
| Resume not tailoring | Check `RESUME_DRIVE_URL` in `.env` is accessible |
| Scheduled task not firing | Verify your OS-level scheduled task is active and that it launches Claude Code CLI from this project directory |
