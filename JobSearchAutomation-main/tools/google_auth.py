"""
Tool: google_auth.py

Purpose:
    Handles Google OAuth 2.0 flow for this project.
    Reads client_secret.json, opens a browser for sign-in on first run,
    saves the token, and refreshes it automatically when it expires.

Usage:
    # Run once to authenticate (opens browser):
    python tools/google_auth.py

    # Import in other tools to get credentials:
    from tools.google_auth import get_credentials

Scopes requested (restricted to only what this project needs):
    - drive.file     : Access only to files this app creates or uploads
    - spreadsheets   : Read and write Google Sheets
    - gmail.send     : Send email on the user's behalf (notifications only — cannot read mail)

Credential paths:
    Client secret : ~/.config/gws/client_secret.json
                    (downloaded from Google Cloud Console during onboarding)
    Token         : ~/.config/gws/token.json
                    (created automatically after first sign-in, never share this)

Exit codes:
    0 = authenticated successfully
    1 = client_secret.json missing or auth failed
"""

import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.send",
]

CONFIG_DIR = Path.home() / ".config" / "gws"
CLIENT_SECRET_PATH = CONFIG_DIR / "client_secret.json"
TOKEN_PATH = CONFIG_DIR / "token.json"


def get_credentials() -> Credentials:
    """
    Load and return valid Google credentials.

    On first call: opens a browser window for Google sign-in and saves the token.
    On subsequent calls: loads the saved token, refreshing it silently if expired.

    Returns:
        google.oauth2.credentials.Credentials — ready to use with Google API clients

    Raises:
        FileNotFoundError if client_secret.json is missing
        google.auth.exceptions.RefreshError if token cannot be refreshed
    """
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_PATH.exists():
                raise FileNotFoundError(
                    f"\nClient secret not found at: {CLIENT_SECRET_PATH}\n"
                    "Download client_secret.json from Google Cloud Console and place it there.\n"
                    "See workflows/onboarding_google.md for setup instructions."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())

    return creds


def check_auth() -> bool:
    """
    Check whether valid credentials exist without triggering a new auth flow.

    Returns:
        True if credentials are valid (or refreshable), False otherwise.
    """
    if not TOKEN_PATH.exists():
        return False
    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        if creds.valid:
            return True
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json())
            return True
    except Exception:
        pass
    return False


def main():
    print("Checking Google authentication...")
    if check_auth():
        print("Already authenticated. No action needed.")
        sys.exit(0)

    print("Opening browser for Google sign-in...")
    print("Sign in with your Google account and approve access.")
    try:
        get_credentials()
        print("Authentication successful. Token saved.")
        sys.exit(0)
    except FileNotFoundError as e:
        print(str(e))
        sys.exit(1)
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
