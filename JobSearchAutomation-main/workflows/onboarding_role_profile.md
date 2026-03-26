# Workflow: Onboarding Role Profile

## Objective
Use `ideal_role.json` to populate job-search criteria automatically, and optionally store richer role-profile
fields when they are available.

## When This Runs
- Only read this file if `ideal_role.json` exists and search criteria are missing.

## Step 1: Read the File
Tell the user:
`I found your ideal role profile. Let me read it and set up your search criteria automatically.`

Read `ideal_role.json`.

Extract:
- `role_category.name`
- `function.name`
- `sector.name`
- `org_size.name`
- `job_level.name`
- `job_level.type`
- useful language from the description fields

## Step 2: Generate Search Inputs
Generate job title variants from:
- `role_category.name`
- `function.name`
- `job_level.name`

Use the description fields to identify actual job-posting vocabulary and extract keywords.

At minimum, this workflow must produce:
- `JOB_TITLES`
- `KEYWORDS`

If the profile contains the richer fields, also save:
- `ROLE_FUNCTION`
- `ROLE_CATEGORY`
- `SECTOR`
- `ORG_SIZE`
- `JOB_LEVEL`
- `JOB_LEVEL_TYPE`

## Step 3: Confirm With the User
Show the user:
- role
- function
- sector
- org size
- generated search titles
- extracted keywords

Ask:
`Does this look right? You can say 'yes' to continue, or tell me what to change.`

Wait for confirmation and adjust if needed.

## Step 4: Save to `.env`
Save:
- `JOB_TITLES`
- `KEYWORDS`

If available from the file, also save:
- `ROLE_FUNCTION`
- `ROLE_CATEGORY`
- `SECTOR`
- `ORG_SIZE`
- `JOB_LEVEL`
- `JOB_LEVEL_TYPE`

## Step 5: Ask for the Two Search Filters Not in the Profile
Ask these even if `ideal_role.json` was present:

1. `What location? Enter a city/state (for example Austin, TX) or 'Remote'.`
   Save to `LOCATION`

2. `What's your minimum acceptable salary? Enter a number (for example 80000) or 'any' to skip.`
   Save to `SALARY_MIN`
   Use `0` for `any`
