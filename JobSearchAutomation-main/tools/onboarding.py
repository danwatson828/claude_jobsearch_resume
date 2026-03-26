"""
Tool: onboarding.py

Purpose:
    Handle the mechanical tasks of the onboarding workflow:
    creating the project Drive folder and reading/writing .env values.

    The agent (Claude) handles all user interaction and decision-making.
    This tool handles the file I/O and Drive API call.

Usage:
    # Create the project folder in Google Drive
    python tools/onboarding.py --action create_project_folder

    # Write a key-value pair to .env
    python tools/onboarding.py --action write_env --key RESUME_DRIVE_URL --value "https://..."

    # Read a key from .env
    python tools/onboarding.py --action read_env --key JOB_TITLES

    # Check which required .env fields are missing
    python tools/onboarding.py --action check_env

Parameters:
    --action  One of: create_project_folder | write_env | read_env | check_env
    --key     .env variable name (for write_env / read_env)
    --value   Value to write (for write_env)

Returns:
    create_project_folder -> prints Google Drive folder ID to stdout
    write_env             -> prints "ok" to stdout
    read_env              -> prints the value to stdout (empty string if not set)
    check_env             -> prints JSON array of missing field names to stdout
                              (empty array [] means onboarding is complete)

Required .env fields checked by check_env:
    DRIVE_FOLDER_ID
    RESUME_DRIVE_URL
    USER_EMAIL
    JOB_TITLES
    LOCATION
    SALARY_MIN
    KEYWORDS
    GOOGLE_SHEET_ID

Auth:
    Google auth is handled by tools.google_auth using machine-local files in
    ~/.config/gws/ (client_secret.json and token.json).
    NEVER hardcode credentials here. Always load them through the shared auth flow.

.env format:
    KEY=value
    One per line. Values containing spaces do NOT need quotes in this tool's
    write implementation, but the agent should strip quotes when reading.

Security notes:
    - This tool reads and writes .env and may create the project Drive folder.
    - Google OAuth files live outside the project and are managed by tools.google_auth.
    - .env must never be committed to version control.

Exit codes:
    0 = success
    1 = error (details on stderr)
"""

import argparse
import json
import sys
import os
from pathlib import Path

REQUIRED_ENV_FIELDS = [
    "DRIVE_FOLDER_ID",
    "RESUME_DRIVE_URL",
    "USER_EMAIL",
    "JOB_TITLES",
    "LOCATION",
    "SALARY_MIN",
    "KEYWORDS",
    "GOOGLE_SHEET_ID",
]

ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")


# ---------------------------------------------------------------------------
# .env helpers
# ---------------------------------------------------------------------------

def read_env_file() -> dict:
    """
    Parse .env into a dict. Returns empty dict if file doesn't exist.
    Ignores blank lines and lines starting with #.
    """
    result = {}
    if not os.path.exists(ENV_PATH):
        return result
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                result[key.strip()] = value.strip()
    return result


def write_env_value(key: str, value: str) -> None:
    """
    Write or update a single key in .env.
    If the key already exists, its line is updated in place.
    If it doesn't exist, it's appended.

    Args:
        key:   Environment variable name
        value: Value to set (strings with spaces are stored unquoted)
    """
    env = read_env_file()
    env[key] = value

    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

    # Update existing key if present
    updated = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}=") or line.strip() == key:
            lines[i] = f"{key}={value}\n"
            updated = True
            break

    if not updated:
        lines.append(f"{key}={value}\n")

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)


# ---------------------------------------------------------------------------
# Drive project folder
# ---------------------------------------------------------------------------

PROJECT_FOLDER_NAME = "JobSearchAutomation"


def create_project_folder() -> str:
    """
    Find or create the top-level 'JobSearchAutomation' folder in Google Drive.
    Returns its ID. All project artifacts go inside this folder.

    Returns:
        Google Drive folder ID string
    """
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from googleapiclient.discovery import build
    from tools.google_auth import get_credentials
    from tools.drive_helpers import get_or_create_folder

    creds = get_credentials()
    service = build("drive", "v3", credentials=creds)
    return get_or_create_folder(service, PROJECT_FOLDER_NAME)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Onboarding helper: project folder and .env management.")
    parser.add_argument("--action", required=True,
                        choices=["create_project_folder", "write_env", "read_env", "check_env"])
    parser.add_argument("--key", default=None, help=".env key for read_env / write_env")
    parser.add_argument("--value", default=None, help="Value for write_env")
    args = parser.parse_args()

    try:
        if args.action == "create_project_folder":
            folder_id = create_project_folder()
            print(folder_id)

        elif args.action == "write_env":
            if not args.key:
                print("ERROR: --key required for write_env", file=sys.stderr)
                sys.exit(1)
            write_env_value(args.key, args.value or "")
            print("ok")

        elif args.action == "read_env":
            if not args.key:
                print("ERROR: --key required for read_env", file=sys.stderr)
                sys.exit(1)
            env = read_env_file()
            print(env.get(args.key, ""))

        elif args.action == "check_env":
            env = read_env_file()
            missing = [f for f in REQUIRED_ENV_FIELDS if not env.get(f)]
            print(json.dumps(missing))

        sys.exit(0)

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
