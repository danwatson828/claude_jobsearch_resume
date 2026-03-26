# Workflow: Onboarding Manual Criteria

## Objective
Collect only the search inputs the automation actually needs when `ideal_role.json` is not being used.

## When This Runs
- Only read this file if search criteria are missing and the role-profile file path is not being used.

## Manual Path
Tell the user:
`I can keep this manual setup lightweight. I only need the fields the automation actually uses for searching.`

Ask one question at a time. After each answer, save it to `.env`.

1. `What job titles should I search for? You can list multiple, separated by commas.`
   Save to `JOB_TITLES`

2. `What location? Enter a city/state (for example Austin, TX) or 'Remote'.`
   Save to `LOCATION`

3. `What's your minimum acceptable salary? Enter a number (for example 80000) or 'any' to skip.`
   Save to `SALARY_MIN`
   Use `0` for `any`

4. `Any keywords to target or exclude? Format: include:python,sql exclude:unpaid,internship - or press Enter to skip.`
   Save to `KEYWORDS`

## Important
Do not ask for these fields in the manual path:
- `ROLE_FUNCTION`
- `ROLE_CATEGORY`
- `SECTOR`
- `ORG_SIZE`
- `JOB_LEVEL`
- `JOB_LEVEL_TYPE`

Those fields are optional metadata now. They are not required for the search workflow to run.
