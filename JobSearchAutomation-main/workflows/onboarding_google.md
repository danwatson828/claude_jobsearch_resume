# Workflow: Onboarding Google

## Objective
Connect the project to the user's Google account, save `USER_EMAIL`, and ensure the Drive project folder
exists so resume upload and sheet creation can work.

## When This Runs
- Only read this file if Google-related setup is missing or incomplete.

## Behavior
Tell the user:
`Now I need to connect this project to your Google account so it can create and manage your Google Sheets and upload your resume to Drive. You're setting up your own personal app, not granting access to a third-party company app. It's free, it takes about 5 minutes, and you only do it once on this machine.`

Run `python tools/google_auth.py` to check whether auth is already valid.

### If Already Authenticated and `USER_EMAIL` Is Present
Tell the user:
`Google is already connected.`

If `DRIVE_FOLDER_ID` is missing:
- Tell the user:
  `I'm going to create a folder in your Google Drive called 'JobSearchAutomation'. Your resume, job tracker sheet, and tailored resumes will live inside it.`
- Run `python tools/onboarding.py --action create_project_folder`
- Save the returned folder ID with
  `python tools/onboarding.py --action write_env --key DRIVE_FOLDER_ID --value "<folder_id>"`

Then exit this workflow.

### If Already Authenticated but `USER_EMAIL` Is Missing
Tell the user:
`Your Google connection is active, but I need to add one permission so I can email you when resumes are ready. I'll open a browser briefly - just sign in and approve the updated permissions.`

Delete the token file, then re-run `python tools/google_auth.py`.
After re-auth completes, ask:
`What's the Gmail address you just signed in with? I'll use it to email you when a tailored resume is ready.`

Save it with:
`python tools/onboarding.py --action write_env --key USER_EMAIL --value "<email>"`

If `DRIVE_FOLDER_ID` is missing, create and save it as above.

### If Not Authenticated
Walk the user through this sequence.

1. Create a Google Cloud project:
   `https://console.cloud.google.com/projectcreate`

2. Enable these APIs:
   - `https://console.cloud.google.com/apis/library/drive.googleapis.com`
   - `https://console.cloud.google.com/apis/library/sheets.googleapis.com`

3. Configure OAuth consent and create a desktop OAuth client:
   - Consent screen: `https://console.cloud.google.com/apis/credentials/consent`
   - App name: `Job Search Automation`
   - Audience: `External`
   - App type: `Desktop app`
   - Add the user's Google email as a test user
   - Create a desktop client and download the JSON credentials file

4. Have the user move the downloaded JSON to:
   `C:\Users\<username>\.config\gws\client_secret.json`

5. Have the user run on their machine:
   - `pip install -r requirements.txt`
   - `python tools/google_auth.py`

6. Ask:
   `What's the Gmail address you just signed in with? I'll use it to email you when a tailored resume is ready.`

7. Save the email:
   `python tools/onboarding.py --action write_env --key USER_EMAIL --value "<email>"`

8. Create the Drive project folder:
   - `python tools/onboarding.py --action create_project_folder`
   - save it with `python tools/onboarding.py --action write_env --key DRIVE_FOLDER_ID --value "<folder_id>"`

Tell the user:
`Done - your Google connection and project folder are ready.`

## Notes
- Google auth is machine-local and reused on future runs
- Do not create the Google Sheet here; `workflows/onboarding_finalize.md` handles that
