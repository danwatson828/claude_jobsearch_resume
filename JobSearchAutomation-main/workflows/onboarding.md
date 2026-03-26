# Workflow: Onboarding

## Objective
Collect the minimum required configuration for the automation, save it to `.env`, and hand control
back to `run.md` so the user can choose whether to run an initial search or set up recurring runs with `/loop`.

This file is intentionally short. It is a router. Read additional onboarding workflow files only when
their branch is actually needed.

## When This Runs
- Called by `run.md` every time.
- Skips itself if required setup is already complete.
- Should never block a scheduled run.

## Required .env Fields
These fields must exist for onboarding to be considered complete:
```
DRIVE_FOLDER_ID
RESUME_DRIVE_URL
USER_EMAIL
JOB_TITLES
LOCATION
SALARY_MIN
KEYWORDS
GOOGLE_SHEET_ID
```

## Optional Role-Profile Fields
These are useful when `ideal_role.json` is present, but they are not required for the automation to run:
```
ROLE_FUNCTION
ROLE_CATEGORY
SECTOR
ORG_SIZE
JOB_LEVEL
JOB_LEVEL_TYPE
```

## Routing Rules

### Step 1: Check if Onboarding Is Already Complete
Run `python tools/onboarding.py --action check_env` silently.

- If the output is `[]`: log `Already set up. Skipping onboarding.` and exit immediately.
  Return control to `run.md`.
- If the output contains missing fields: continue.

### Step 2: Load Only the Needed Sub-Workflows
Use the missing fields and current machine state to decide what to read next.

Read `workflows/onboarding_dependencies.md` if:
- onboarding is not complete

Read `workflows/onboarding_google.md` if any of these are true:
- `DRIVE_FOLDER_ID` is missing
- `GOOGLE_SHEET_ID` is missing
- `RESUME_DRIVE_URL` is missing and Google auth may be needed
- `USER_EMAIL` is missing
- Google auth is missing, invalid, or missing the Gmail send scope

For job-search criteria, choose exactly one path:
- Read `workflows/onboarding_role_profile.md` if `ideal_role.json` exists and any of
  `JOB_TITLES`, `KEYWORDS`, `LOCATION`, or `SALARY_MIN` are missing
- Otherwise read `workflows/onboarding_manual_criteria.md` if any of
  `JOB_TITLES`, `KEYWORDS`, `LOCATION`, or `SALARY_MIN` are missing

Read `workflows/onboarding_resume.md` if `RESUME_DRIVE_URL` is missing.

Read `workflows/onboarding_finalize.md` if `GOOGLE_SHEET_ID` is missing, or after the other steps
to produce the closing summary.

### Step 3: Stop After Setup
When the needed sub-workflows are complete, return control to `run.md`.

Do not start `workflows/search_jobs.md` from onboarding.
After onboarding completes, the default behavior is to stop and say:

`Okay, you're all set. If you would like, I can perform an initial job search automation now.`

Only continue into `workflows/search_jobs.md` if the user explicitly says yes.
