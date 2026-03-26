# Workflow: Onboarding Finalize

## Objective
Create the Google Sheet if needed and present the final setup summary.

## When This Runs
- Read this file only after dependencies, Google setup, criteria, and resume setup are complete enough.

## Step 1: Google Sheet Setup
If `GOOGLE_SHEET_ID` is missing:
- read `DRIVE_FOLDER_ID` from `.env`
- run `python tools/sheets.py --action create --folder_id "<DRIVE_FOLDER_ID>"`
- save the returned sheet ID as `GOOGLE_SHEET_ID`

## Step 2: Confirm to the User
Tell the user:
`You're all set. Here's what I saved:`

- Job titles: `[JOB_TITLES]`
- Location: `[LOCATION]`
- Salary minimum: `[SALARY_MIN]`
- Keywords: `[KEYWORDS]`
- Resume on Drive: `[RESUME_DRIVE_URL]`
- Job tracker sheet: `https://docs.google.com/spreadsheets/d/[GOOGLE_SHEET_ID]`
- All files are in the `JobSearchAutomation` Drive folder: `https://drive.google.com/drive/folders/[DRIVE_FOLDER_ID]`

Then remind the user:
`To keep using this project, open it in Claude Code for VS Code or run Claude Code from the CLI in this folder. If you want automatic recurring runs, I can help set that up using the /loop slash command. Examples: /loop 5m check the deploy, /loop 30m /babysit-prs, /loop 1h run the workflow.`

Then return control to `run.md`.

Do not run `workflows/search_jobs.md` from this file.
