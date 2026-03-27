"""
Tool: sheets.py

Purpose:
    Create and manage the Job Tracker Google Sheet.
    Handles sheet creation, row appending, URL deduplication, and notes updates.

Usage:
    # Create the sheet (returns Sheet ID):
    python tools/sheets.py --action create

    # Create the sheet inside a specific Drive folder:
    python tools/sheets.py --action create --folder_id "1abc..."

    # Get all URLs already in the sheet (for deduplication):
    python tools/sheets.py --action get_urls --sheet_id SHEET_ID

    # Append a new job row (returns row number):
    python tools/sheets.py --action append_row --sheet_id SHEET_ID \
        --row '["2026-03-08","Software Engineer","Acme","Austin TX","$120k","2026-03-05","https://...","New",""]'

    # Write a URL into the Notes column for a specific row:
    python tools/sheets.py --action update_notes --sheet_id SHEET_ID \
        --row_num 5 --notes "https://drive.google.com/..."

    # Write a cover letter URL into column K for a specific row:
    python tools/sheets.py --action update_cover_letter --sheet_id SHEET_ID \
        --row_num 5 --notes "https://drive.google.com/..."

    # Create the Manual Jobs tab (no-op if already exists):
    python tools/sheets.py --action create_manual_tab --sheet_id SHEET_ID

    # Create (or refresh) the Dashboard tab with live outcome counts:
    python tools/sheets.py --action create_dashboard_tab --sheet_id SHEET_ID

    # Get pending manual jobs (Status blank):
    python tools/sheets.py --action get_manual_jobs --sheet_id SHEET_ID

    # Update a Manual Jobs tab row with system-filled values:
    python tools/sheets.py --action update_manual_job --sheet_id SHEET_ID \
        --row_num N [--main_row N] [--status "Done"] [--resume_url "..."] [--cover_url "..."]

Parameters:
    --action      One of: create | get_urls | append_row | update_notes | update_cover_letter
                          | create_manual_tab | get_manual_jobs | update_manual_job
    --sheet_id    Google Sheet ID (stored as GOOGLE_SHEET_ID in .env)
    --folder_id   Optional Drive folder ID for create action (stored as DRIVE_FOLDER_ID in .env)
    --row         JSON array of cell values for append_row
    --row_num     Integer row number for update_notes / update_cover_letter / update_manual_job (1-indexed)
    --notes       String to write into the Notes or Cover Letter column
    --main_row    Integer row number in the main Jobs tab (for update_manual_job)
    --resume_url  Resume Drive URL (for update_manual_job)
    --cover_url   Cover letter Drive URL (for update_manual_job)

Returns:
    create               → prints Sheet ID to stdout
    get_urls             → prints JSON array of URL strings
    append_row           → prints the new row number (int)
    update_notes         → prints "ok"
    update_cover_letter  → prints "ok"
    create_manual_tab    → prints "ok" or "exists"
    get_manual_jobs      → prints JSON array of pending job objects
    update_manual_job    → prints "ok"
    create_dashboard_tab → prints "ok"

Sheet schema (column order is fixed — do not change):
    A: Date Found
    B: Job Title
    C: Company
    D: Location
    E: Salary
    F: Date Posted
    G: URL          ← used for deduplication
    H: Status       ← default "New"
    I: Notes        ← tailored resume URL written here
    J: Job ID       ← stable hash for deduplication
    K: Cover Letter ← cover letter Drive URL written here

Manual Jobs tab schema (column order is fixed — do not change):
    A: Company      ← user fills
    B: Job Title    ← user fills
    C: URL          ← user fills
    D: Location     ← user fills (optional)
    E: Salary       ← user fills (optional)
    F: Main Row     ← system: row # in main Jobs tab
    G: Status       ← system: blank → Processing → Done / Error
    H: Resume URL   ← system: tailored resume Drive URL
    I: Cover Letter ← system: cover letter Drive URL

Exit codes:
    0 = success
    1 = error (details on stderr)
"""

import argparse
import json
import sys
from pathlib import Path

from googleapiclient.discovery import build

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.google_auth import get_credentials

SHEET_NAME = "Jobs"
HEADERS = [
    "Date Found", "Job Title", "Company", "Location", "Salary",
    "Date Posted", "URL", "Status", "Notes", "Job ID", "Cover Letter",
]

MANUAL_SHEET_NAME = "Manual Jobs"
MANUAL_HEADERS = [
    "Company", "Job Title", "URL", "Location", "Salary",
    "Main Row", "Status", "Resume URL", "Cover Letter",
]

DASHBOARD_SHEET_NAME = "Dashboard"

# Status labels tracked on the dashboard (order determines row order)
DASHBOARD_STATUSES = [
    "New",
    "Applied",
    "Phone Screen",
    "Interview",
    "Final Round",
    "Offer",
    "Rejected",
    "Withdrawn",
]


def extract_job_hash(job_id: str) -> str:
    """
    Extract the stable unique job hash from an Indeed job ID.

    Indeed job IDs follow the pattern:
        5-cmh1-0-{session_id}-{job_hash}[---{tracking}]

    The job_hash (5th segment) is consistent across searches for the same
    posting even when session_id and short URLs differ.

    Args:
        job_id: Full Indeed job ID string

    Returns:
        Lowercase hex job hash string, or the full job_id if parsing fails
    """
    parts = job_id.split("-")
    if len(parts) >= 5:
        return parts[4].split("---")[0].lower()
    return job_id.lower()


def _sheets_service():
    return build("sheets", "v4", credentials=get_credentials())


def _drive_service():
    return build("drive", "v3", credentials=get_credentials())


def create_sheet(title: str = "Job Tracker", folder_id: str = None) -> str:
    """
    Create a new Google Sheet named 'Job Tracker' with the correct headers.
    If folder_id is provided, moves the sheet into that Drive folder.

    Args:
        title:     Spreadsheet title (default: "Job Tracker")
        folder_id: Optional Drive folder ID to place the sheet in

    Returns:
        Sheet ID string
    """
    svc = _sheets_service()

    spreadsheet = svc.spreadsheets().create(
        body={
            "properties": {"title": title},
            "sheets": [{"properties": {"title": SHEET_NAME}}],
        }
    ).execute()

    sheet_id = spreadsheet["spreadsheetId"]

    # Write header row
    svc.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"{SHEET_NAME}!A1",
        valueInputOption="RAW",
        body={"values": [HEADERS]},
    ).execute()

    # Move into project folder if specified
    if folder_id:
        drive_svc = _drive_service()
        # Get current parents so we can remove them (typically "root")
        file_meta = drive_svc.files().get(
            fileId=sheet_id, fields="parents"
        ).execute()
        current_parents = ",".join(file_meta.get("parents", []))
        drive_svc.files().update(
            fileId=sheet_id,
            addParents=folder_id,
            removeParents=current_parents,
            fields="id,parents",
        ).execute()

    return sheet_id


def get_existing_urls(sheet_id: str) -> list:
    """
    Return all URLs in column G (skipping the header row).
    Used to filter out jobs already in the sheet.

    Args:
        sheet_id: Google Sheet ID

    Returns:
        List of URL strings (may be empty)
    """
    svc = _sheets_service()
    result = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"{SHEET_NAME}!G2:G",
    ).execute()
    values = result.get("values", [])
    return [row[0] for row in values if row]


def get_existing_job_hashes(sheet_id: str) -> set:
    """
    Return the set of job hashes already stored in column J.
    Used for definitive deduplication — job hashes are stable across searches
    even when Indeed generates different short URLs for the same posting.

    Args:
        sheet_id: Google Sheet ID

    Returns:
        Set of job hash strings (may be empty)
    """
    svc = _sheets_service()
    result = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"{SHEET_NAME}!J2:J",
    ).execute()
    values = result.get("values", [])
    return {row[0].lower() for row in values if row and row[0]}


def append_row(sheet_id: str, row: list) -> int:
    """
    Append a job row to the sheet and return the row number.

    Args:
        sheet_id: Google Sheet ID
        row: List of 10 values matching the sheet column order:
             [date_found, title, company, location, salary,
              date_posted, url, status, notes, job_id_hash]

    Returns:
        1-indexed integer row number of the newly appended row
    """
    svc = _sheets_service()

    # Find the next empty row by counting existing values in column A
    result = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"{SHEET_NAME}!A:A",
    ).execute()
    existing = result.get("values", [])
    next_row = len(existing) + 1  # 1-indexed, one past the last populated row

    # Write directly to the next empty row
    svc.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"{SHEET_NAME}!A{next_row}",
        valueInputOption="RAW",
        body={"values": [row]},
    ).execute()

    return next_row


def update_notes(sheet_id: str, row_num: int, notes: str) -> None:
    """
    Write a value into the Notes column (column I) for a specific row.

    Args:
        sheet_id: Google Sheet ID
        row_num:  1-indexed row number to update
        notes:    String to write (typically a Google Drive or Doc URL)
    """
    svc = _sheets_service()
    svc.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"{SHEET_NAME}!I{row_num}",
        valueInputOption="RAW",
        body={"values": [[notes]]},
    ).execute()


def update_cover_letter(sheet_id: str, row_num: int, url: str) -> None:
    """
    Write a cover letter Drive URL into column K for a specific row.

    Args:
        sheet_id: Google Sheet ID
        row_num:  1-indexed row number to update
        url:      Cover letter Drive URL
    """
    svc = _sheets_service()
    svc.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"{SHEET_NAME}!K{row_num}",
        valueInputOption="RAW",
        body={"values": [[url]]},
    ).execute()


def create_manual_tab(sheet_id: str) -> str:
    """
    Add a "Manual Jobs" tab to the spreadsheet if it does not already exist.
    Writes a frozen header row on creation.

    Args:
        sheet_id: Google Sheet ID

    Returns:
        "ok" if created, "exists" if tab was already present
    """
    svc = _sheets_service()

    # Check existing sheets
    meta = svc.spreadsheets().get(spreadsheetId=sheet_id, fields="sheets.properties.title").execute()
    existing = [s["properties"]["title"] for s in meta.get("sheets", [])]
    if MANUAL_SHEET_NAME in existing:
        return "exists"

    # Add the sheet tab
    svc.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": MANUAL_SHEET_NAME}}}]},
    ).execute()

    # Write header row
    svc.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'{MANUAL_SHEET_NAME}'!A1",
        valueInputOption="RAW",
        body={"values": [MANUAL_HEADERS]},
    ).execute()

    # Freeze header row
    # Need sheet ID (gid) of the new tab
    meta2 = svc.spreadsheets().get(spreadsheetId=sheet_id, fields="sheets.properties").execute()
    gid = None
    for s in meta2.get("sheets", []):
        if s["properties"]["title"] == MANUAL_SHEET_NAME:
            gid = s["properties"]["sheetId"]
            break

    if gid is not None:
        svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={
                "requests": [{
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": gid,
                            "gridProperties": {"frozenRowCount": 1},
                        },
                        "fields": "gridProperties.frozenRowCount",
                    }
                }]
            },
        ).execute()

    return "ok"


def get_manual_jobs(sheet_id: str) -> list:
    """
    Return all rows from the Manual Jobs tab where column G (Status) is blank.

    Args:
        sheet_id: Google Sheet ID

    Returns:
        List of dicts with keys: manual_row, company, job_title, url, location, salary
    """
    svc = _sheets_service()
    result = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"'{MANUAL_SHEET_NAME}'!A2:I",
    ).execute()
    rows = result.get("values", [])

    pending = []
    for i, row in enumerate(rows):
        # Pad to 9 columns
        row = row + [""] * (9 - len(row))
        company, job_title, url, location, salary, main_row, status = (
            row[0], row[1], row[2], row[3], row[4], row[5], row[6]
        )
        if status.strip() == "":
            pending.append({
                "manual_row": i + 2,  # 1-indexed, offset by header row
                "company": company,
                "job_title": job_title,
                "url": url,
                "location": location,
                "salary": salary,
            })
    return pending


def update_manual_job(
    sheet_id: str,
    row_num: int,
    company: str = None,
    job_title: str = None,
    main_row: int = None,
    status: str = None,
    resume_url: str = None,
    cover_url: str = None,
    location: str = None,
    salary: str = None,
) -> None:
    """
    Write system-filled values back to a row in the Manual Jobs tab.

    Args:
        sheet_id:   Google Sheet ID
        row_num:    1-indexed row number in the Manual Jobs tab
        company:    Company name (column A)
        job_title:  Job title (column B)
        main_row:   Row number in the main Jobs tab (column F)
        status:     Status string (column G)
        resume_url: Tailored resume Drive URL (column H)
        cover_url:  Cover letter Drive URL (column I)
        location:   Job location (column D)
        salary:     Salary/compensation range (column E)
    """
    svc = _sheets_service()

    updates = []
    if company is not None:
        updates.append({
            "range": f"'{MANUAL_SHEET_NAME}'!A{row_num}",
            "values": [[company]],
        })
    if job_title is not None:
        updates.append({
            "range": f"'{MANUAL_SHEET_NAME}'!B{row_num}",
            "values": [[job_title]],
        })
    if location is not None:
        updates.append({
            "range": f"'{MANUAL_SHEET_NAME}'!D{row_num}",
            "values": [[location]],
        })
    if salary is not None:
        updates.append({
            "range": f"'{MANUAL_SHEET_NAME}'!E{row_num}",
            "values": [[salary]],
        })
    if main_row is not None:
        updates.append({
            "range": f"'{MANUAL_SHEET_NAME}'!F{row_num}",
            "values": [[main_row]],
        })
    if status is not None:
        updates.append({
            "range": f"'{MANUAL_SHEET_NAME}'!G{row_num}",
            "values": [[status]],
        })
    if resume_url is not None:
        updates.append({
            "range": f"'{MANUAL_SHEET_NAME}'!H{row_num}",
            "values": [[resume_url]],
        })
    if cover_url is not None:
        updates.append({
            "range": f"'{MANUAL_SHEET_NAME}'!I{row_num}",
            "values": [[cover_url]],
        })

    if updates:
        svc.spreadsheets().values().batchUpdate(
            spreadsheetId=sheet_id,
            body={"valueInputOption": "RAW", "data": updates},
        ).execute()


def create_dashboard_tab(sheet_id: str) -> str:
    """
    Create (or replace) a Dashboard tab with live COUNTIF formulas
    that summarize application outcomes from the Jobs tab Status column.

    The formulas auto-update whenever statuses are changed in the sheet —
    no need to re-run this script after creation.

    Args:
        sheet_id: Google Sheet ID

    Returns:
        "ok" if created/refreshed, "error" on failure
    """
    svc = _sheets_service()

    # Get existing sheet metadata
    meta = svc.spreadsheets().get(
        spreadsheetId=sheet_id,
        fields="sheets.properties",
    ).execute()
    sheets_meta = meta.get("sheets", [])
    existing_titles = [s["properties"]["title"] for s in sheets_meta]

    # Create the tab if it doesn't exist
    if DASHBOARD_SHEET_NAME not in existing_titles:
        svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": DASHBOARD_SHEET_NAME}}}]},
        ).execute()
        # Refresh metadata to get new gid
        meta = svc.spreadsheets().get(
            spreadsheetId=sheet_id,
            fields="sheets.properties",
        ).execute()
        sheets_meta = meta.get("sheets", [])

    # Find the dashboard tab's gid
    dash_gid = None
    for s in sheets_meta:
        if s["properties"]["title"] == DASHBOARD_SHEET_NAME:
            dash_gid = s["properties"]["sheetId"]
            break

    # ------------------------------------------------------------------ #
    # Build cell values / formulas
    # ------------------------------------------------------------------ #
    # Row 1  – title
    # Row 2  – blank
    # Row 3  – column headers
    # Row 4  – Total Tracked
    # Row 5  – blank spacer
    # Row 6+ – one row per status label
    # Last+1 – blank
    # Last+2 – conversion rates header
    # Last+3 – Interview Rate
    # Last+4 – Offer Rate

    status_data_rows = []
    for label in DASHBOARD_STATUSES:
        formula = f'=COUNTIF(Jobs!H:H,"{label}")'
        status_data_rows.append([label, formula])

    # Total = everything in column H except the header (non-empty cells - 1 for header)
    total_formula = "=COUNTA(Jobs!H:H)-1"

    # Interview rate = (Interview + Final Round + Offer) / Applied  *100
    applied_labels = '"Applied","Phone Screen","Interview","Final Round","Offer","Rejected","Withdrawn"'
    applied_formula = f"=COUNTIFS(Jobs!H:H,\"Applied\")+COUNTIFS(Jobs!H:H,\"Phone Screen\")+COUNTIFS(Jobs!H:H,\"Interview\")+COUNTIFS(Jobs!H:H,\"Final Round\")+COUNTIFS(Jobs!H:H,\"Offer\")+COUNTIFS(Jobs!H:H,\"Rejected\")+COUNTIFS(Jobs!H:H,\"Withdrawn\")"
    interview_rate_formula = (
        '=IF(COUNTIFS(Jobs!H:H,"Applied")+COUNTIFS(Jobs!H:H,"Phone Screen")'
        '+COUNTIFS(Jobs!H:H,"Interview")+COUNTIFS(Jobs!H:H,"Final Round")'
        '+COUNTIFS(Jobs!H:H,"Offer")+COUNTIFS(Jobs!H:H,"Rejected")'
        '+COUNTIFS(Jobs!H:H,"Withdrawn")=0,"—",'
        'TEXT((COUNTIFS(Jobs!H:H,"Interview")+COUNTIFS(Jobs!H:H,"Final Round")'
        '+COUNTIFS(Jobs!H:H,"Offer"))/'
        '(COUNTIFS(Jobs!H:H,"Applied")+COUNTIFS(Jobs!H:H,"Phone Screen")'
        '+COUNTIFS(Jobs!H:H,"Interview")+COUNTIFS(Jobs!H:H,"Final Round")'
        '+COUNTIFS(Jobs!H:H,"Offer")+COUNTIFS(Jobs!H:H,"Rejected")'
        '+COUNTIFS(Jobs!H:H,"Withdrawn"))*100,"0.0")&"%")'
    )
    offer_rate_formula = (
        '=IF(COUNTIFS(Jobs!H:H,"Applied")+COUNTIFS(Jobs!H:H,"Phone Screen")'
        '+COUNTIFS(Jobs!H:H,"Interview")+COUNTIFS(Jobs!H:H,"Final Round")'
        '+COUNTIFS(Jobs!H:H,"Offer")+COUNTIFS(Jobs!H:H,"Rejected")'
        '+COUNTIFS(Jobs!H:H,"Withdrawn")=0,"—",'
        'TEXT(COUNTIFS(Jobs!H:H,"Offer")/'
        '(COUNTIFS(Jobs!H:H,"Applied")+COUNTIFS(Jobs!H:H,"Phone Screen")'
        '+COUNTIFS(Jobs!H:H,"Interview")+COUNTIFS(Jobs!H:H,"Final Round")'
        '+COUNTIFS(Jobs!H:H,"Offer")+COUNTIFS(Jobs!H:H,"Rejected")'
        '+COUNTIFS(Jobs!H:H,"Withdrawn"))*100,"0.0")&"%")'
    )

    values = (
        [["Job Search Dashboard", ""], ["", ""]]          # rows 1-2
        + [["Status", "Count"]]                            # row 3
        + [["Total Tracked", total_formula]]               # row 4
        + [["", ""]]                                       # row 5
        + status_data_rows                                 # rows 6+
        + [["", ""], ["Conversion Rates", ""], ["Interview Rate (of Applied)", interview_rate_formula], ["Offer Rate (of Applied)", offer_rate_formula]]
    )

    svc.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'{DASHBOARD_SHEET_NAME}'!A1",
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()

    # ------------------------------------------------------------------ #
    # Formatting
    # ------------------------------------------------------------------ #
    def _cell_fmt(row, col, bold=False, font_size=None, bg_rgb=None, fg_rgb=None):
        """Build a repeatCell formatting request for a single cell."""
        fmt = {"textFormat": {}}
        if bold:
            fmt["textFormat"]["bold"] = True
        if font_size:
            fmt["textFormat"]["fontSize"] = font_size
        if fg_rgb:
            fmt["textFormat"]["foregroundColor"] = fg_rgb
        if bg_rgb:
            fmt["backgroundColor"] = bg_rgb
        return {
            "repeatCell": {
                "range": {
                    "sheetId": dash_gid,
                    "startRowIndex": row,
                    "endRowIndex": row + 1,
                    "startColumnIndex": col,
                    "endColumnIndex": col + 1,
                },
                "cell": {"userEnteredFormat": fmt},
                "fields": "userEnteredFormat(textFormat,backgroundColor)",
            }
        }

    def _row_fmt(row, end_col, bold=False, bg_rgb=None):
        """Build a repeatCell formatting request for a full row range."""
        fmt = {}
        if bold:
            fmt["textFormat"] = {"bold": True}
        if bg_rgb:
            fmt["backgroundColor"] = bg_rgb
        return {
            "repeatCell": {
                "range": {
                    "sheetId": dash_gid,
                    "startRowIndex": row,
                    "endRowIndex": row + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": end_col,
                },
                "cell": {"userEnteredFormat": fmt},
                "fields": "userEnteredFormat(" + ",".join(
                    (["textFormat"] if bold else []) +
                    (["backgroundColor"] if bg_rgb else [])
                ) + ")",
            }
        }

    dark_blue   = {"red": 0.11, "green": 0.27, "blue": 0.49}
    white       = {"red": 1.0,  "green": 1.0,  "blue": 1.0}
    light_grey  = {"red": 0.93, "green": 0.93, "blue": 0.93}
    mid_grey    = {"red": 0.85, "green": 0.85, "blue": 0.85}

    # Row indices (0-based)
    title_row       = 0
    header_row      = 2
    total_row       = 3
    first_status    = 5                          # first DASHBOARD_STATUSES row
    conv_header_row = first_status + len(DASHBOARD_STATUSES) + 1
    interview_row   = conv_header_row + 1
    offer_row       = conv_header_row + 2

    fmt_requests = [
        # Title row — dark blue background, white bold text, larger font
        _row_fmt(title_row, 2, bold=True, bg_rgb=dark_blue),
        _cell_fmt(title_row, 0, bold=True, font_size=14, bg_rgb=dark_blue, fg_rgb=white),
        # Column header row
        _row_fmt(header_row, 2, bold=True, bg_rgb=mid_grey),
        # Total row — slightly shaded
        _row_fmt(total_row, 2, bold=True, bg_rgb=light_grey),
        # Conversion rates section header
        _row_fmt(conv_header_row, 2, bold=True, bg_rgb=mid_grey),
    ]

    # Alternate shading on status rows
    for i, _ in enumerate(DASHBOARD_STATUSES):
        row_idx = first_status + i
        if i % 2 == 0:
            fmt_requests.append(_row_fmt(row_idx, 2, bg_rgb=light_grey))

    # Set column A width to ~200px and column B to ~100px
    fmt_requests += [
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": dash_gid,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 1,
                },
                "properties": {"pixelSize": 220},
                "fields": "pixelSize",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": dash_gid,
                    "dimension": "COLUMNS",
                    "startIndex": 1,
                    "endIndex": 2,
                },
                "properties": {"pixelSize": 110},
                "fields": "pixelSize",
            }
        },
        # Freeze header rows (title + blank + column header)
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": dash_gid,
                    "gridProperties": {"frozenRowCount": 3},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        },
    ]

    svc.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": fmt_requests},
    ).execute()

    return "ok"


def main():
    parser = argparse.ArgumentParser(description="Manage the Job Tracker Google Sheet.")
    parser.add_argument("--action", required=True,
                        choices=["create", "get_urls", "get_job_hashes", "append_row",
                                 "update_notes", "update_cover_letter",
                                 "create_manual_tab", "get_manual_jobs", "update_manual_job",
                                 "create_dashboard_tab"])
    parser.add_argument("--sheet_id", default=None)
    parser.add_argument("--folder_id", default=None,
                        help="Drive folder ID to place the sheet in (for create action)")
    parser.add_argument("--row", default=None, help="JSON array for append_row")
    parser.add_argument("--row_num", type=int, default=None)
    parser.add_argument("--notes", default=None)
    parser.add_argument("--main_row", type=int, default=None,
                        help="Row number in main Jobs tab (for update_manual_job)")
    parser.add_argument("--status", default=None,
                        help="Status string to write (for update_manual_job)")
    parser.add_argument("--resume_url", default=None,
                        help="Tailored resume Drive URL (for update_manual_job)")
    parser.add_argument("--cover_url", default=None,
                        help="Cover letter Drive URL (for update_manual_job)")
    parser.add_argument("--company", default=None,
                        help="Company name (for update_manual_job)")
    parser.add_argument("--job_title", default=None,
                        help="Job title (for update_manual_job)")
    parser.add_argument("--location", default=None,
                        help="Job location (for update_manual_job)")
    parser.add_argument("--salary", default=None,
                        help="Salary/compensation range (for update_manual_job)")
    args = parser.parse_args()

    try:
        if args.action == "create":
            sheet_id = create_sheet(folder_id=args.folder_id)
            print(sheet_id)

        elif args.action == "get_urls":
            urls = get_existing_urls(args.sheet_id)
            print(json.dumps(urls))

        elif args.action == "get_job_hashes":
            hashes = get_existing_job_hashes(args.sheet_id)
            print(json.dumps(list(hashes)))

        elif args.action == "append_row":
            row_data = json.loads(args.row)
            row_num = append_row(args.sheet_id, row_data)
            print(row_num)

        elif args.action == "update_notes":
            update_notes(args.sheet_id, args.row_num, args.notes or "")
            print("ok")

        elif args.action == "update_cover_letter":
            update_cover_letter(args.sheet_id, args.row_num, args.notes or "")
            print("ok")

        elif args.action == "create_manual_tab":
            result = create_manual_tab(args.sheet_id)
            print(result)

        elif args.action == "get_manual_jobs":
            jobs = get_manual_jobs(args.sheet_id)
            print(json.dumps(jobs))

        elif args.action == "update_manual_job":
            update_manual_job(
                args.sheet_id,
                args.row_num,
                company=args.company,
                job_title=args.job_title,
                main_row=args.main_row,
                status=args.status,
                resume_url=args.resume_url,
                cover_url=args.cover_url,
                location=args.location,
                salary=args.salary,
            )
            print("ok")

        elif args.action == "create_dashboard_tab":
            result = create_dashboard_tab(args.sheet_id)
            print(result)

        sys.exit(0)

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
