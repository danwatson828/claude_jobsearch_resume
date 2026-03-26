"""
Tool: drive_upload.py

Purpose:
    Upload a local file to Google Drive and return its shareable URL.
    Only has access to files this app creates (drive.file scope).

Usage:
    # Upload to Drive root:
    python tools/drive_upload.py --file "resume/My Resume.pdf"

    # Upload into a specific folder (pass DRIVE_FOLDER_ID from .env):
    python tools/drive_upload.py --file "resume/My Resume.pdf" --folder_id "1abc..."

Parameters:
    --file       Path to the local file to upload (relative to project root)
    --folder_id  Optional. Google Drive folder ID to upload into.
                 If omitted, uploads to Drive root.

Returns:
    Prints the Google Drive shareable URL to stdout.

Exit codes:
    0 = success
    1 = error (details on stderr)
"""

import argparse
import sys
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Add project root to path so we can import google_auth
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.google_auth import get_credentials


def upload_file(local_path: str, folder_id: str = None) -> str:
    """
    Upload a local file to Google Drive and return its shareable URL.

    Sets sharing to 'anyone with link can view' so the resume URL
    can be accessed when tailoring resumes later.

    Args:
        local_path: Path to the file (relative or absolute)
        folder_id:  Optional Drive folder ID to upload into.
                    If None, uploads to Drive root.

    Returns:
        Google Drive webViewLink URL string

    Raises:
        FileNotFoundError if the local file does not exist
        Exception if the upload fails
    """
    file_path = Path(local_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    creds = get_credentials()
    service = build("drive", "v3", credentials=creds)

    media = MediaFileUpload(str(file_path), resumable=True)
    file_metadata = {"name": file_path.name}
    if folder_id:
        file_metadata["parents"] = [folder_id]

    result = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id,webViewLink")
        .execute()
    )

    file_id = result["id"]

    # Make viewable by anyone with the link
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    return result["webViewLink"]


def main():
    parser = argparse.ArgumentParser(description="Upload a file to Google Drive.")
    parser.add_argument("--file", required=True, help="Path to the file to upload")
    parser.add_argument("--folder_id", default=None,
                        help="Drive folder ID to upload into (optional)")
    args = parser.parse_args()

    try:
        url = upload_file(args.file, folder_id=args.folder_id)
        print(url)
        sys.exit(0)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
