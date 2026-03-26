# Workflow: Onboarding Resume

## Objective
Find the resume file, confirm it is the right one for the target search, upload it to the Drive project folder,
and save `RESUME_DRIVE_URL`.

## When This Runs
- Only read this file if `RESUME_DRIVE_URL` is missing.

## Step 1: Find the Resume
Scan the `resume/` folder for `.pdf`, `.doc`, and `.docx` files. Exclude `README.txt`.

- If exactly one file is found:
  tell the user which file was found and that you are checking it before upload
- If multiple files are found:
  ask which one to use
- If no files are found:
  ask the user to place a file in `resume/` and wait for `done`, then scan again

## Step 2: Lightweight Fit Check
Compare the selected resume against the currently known search target.

Use whatever target context exists:
- always use `JOB_TITLES`
- use `KEYWORDS` if present
- use the richer role-profile fields if they happen to be present

Warn only if the mismatch is obvious:
- recent experience is in a clearly different career track
- the resume lacks most of the role's core skills or domain language
- the document would require heavy reframing rather than normal tailoring

If the mismatch is not obvious, ask:
`Is this the resume you'd like to use?`

If the mismatch is obvious, warn the user and ask whether to continue anyway.

If the user does not want to continue, ask them to replace the file and repeat the step.

## Step 3: Upload
Read `DRIVE_FOLDER_ID` from `.env`:
`python tools/onboarding.py --action read_env --key DRIVE_FOLDER_ID`

Upload the selected file:
`python tools/drive_upload.py --file "resume/<filename>" --folder_id "<DRIVE_FOLDER_ID>"`

Save the returned URL:
`python tools/onboarding.py --action write_env --key RESUME_DRIVE_URL --value "<url>"`
