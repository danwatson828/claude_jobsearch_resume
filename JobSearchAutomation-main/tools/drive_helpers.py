"""
Shared Google Drive folder utilities used by drive_upload, sheets, and tailor_resume.
"""


def get_or_create_folder(service, name: str, parent_id: str = None) -> str:
    """
    Find or create a named folder in Google Drive. Returns the folder ID.

    If parent_id is provided, searches within that parent folder.
    If the folder already exists (was created by this app), returns its ID.
    Otherwise creates it and returns the new ID.

    Args:
        service:   Authenticated Drive v3 service object
        name:      Folder name to find or create
        parent_id: Optional parent folder ID (creates at root if omitted)

    Returns:
        Folder ID string
    """
    query = (
        f"name='{name}' "
        "and mimeType='application/vnd.google-apps.folder' "
        "and trashed=false"
    )
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]

    body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        body["parents"] = [parent_id]

    folder = service.files().create(body=body, fields="id").execute()
    return folder["id"]
