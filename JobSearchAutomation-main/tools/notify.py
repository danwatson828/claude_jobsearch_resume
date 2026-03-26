"""
Tool: notify.py

Purpose:
    Send an email notification to the user when a tailored resume is ready.
    Uses the Gmail API to send from the user's own Gmail account to themselves.
    No third-party service — fully owned by the user.

Usage:
    python tools/notify.py \
        --to "you@gmail.com" \
        --job_title "AI Engineer" \
        --company "Acme Corp" \
        --resume_url "https://drive.google.com/..." \
        --cover_letter_url "https://drive.google.com/..." \
        --job_url "https://www.indeed.com/viewjob?jk=..." \
        --sheet_url "https://docs.google.com/spreadsheets/d/..."

Parameters:
    --to                Recipient email address (typically the user's own Gmail)
    --job_title         Job title of the role
    --company           Company name
    --resume_url        Google Drive URL of the tailored resume
    --cover_letter_url  Google Drive URL of the cover letter (optional)
    --job_url           Indeed URL of the job posting
    --sheet_url         Google Sheets URL of the job tracker

Returns:
    Prints "ok" to stdout on success.

Exit codes:
    0 = sent successfully
    1 = error (details on stderr)

Auth:
    Requires gmail.send scope — added to google_auth.py scopes.
    If the existing token lacks this scope, run python tools/google_auth.py
    to re-authenticate and grant the updated permissions.
"""

import argparse
import base64
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from googleapiclient.discovery import build

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.google_auth import get_credentials


def build_email(to: str, job_title: str, company: str,
                resume_url: str, job_url: str, sheet_url: str,
                cover_letter_url: str = None) -> MIMEMultipart:
    """Construct the notification email as a MIME message."""

    subject = f"Resume ready: {job_title} at {company}"

    cover_letter_plain = f"\nCover Letter:\n{cover_letter_url}\n" if cover_letter_url else ""

    plain = f"""Your tailored resume for {job_title} at {company} is ready.

Tailored Resume:
{resume_url}
{cover_letter_plain}
Job Posting:
{job_url}

Job Tracker Sheet:
{sheet_url}

---
This resume was rewritten to mirror the language and keywords in the job description.
All numbers, dates, and company names are unchanged from your original.

To review or apply, open the resume link above.
"""

    cover_letter_row = ""
    if cover_letter_url:
        cover_letter_row = f"""
  <tr>
    <td style="padding: 10px; border: 1px solid #ddd; background: #f8f9fa; width: 140px;">
      <strong>Cover Letter</strong>
    </td>
    <td style="padding: 10px; border: 1px solid #ddd;">
      <a href="{cover_letter_url}" style="color: #1a73e8;">Open in Google Drive</a>
    </td>
  </tr>"""

    html = f"""<html><body style="font-family: Arial, sans-serif; max-width: 600px; color: #333;">

<h2 style="color: #1a73e8;">Resume ready: {job_title} at {company}</h2>

<p>Your tailored resume has been created and uploaded to Google Drive.</p>

<table style="border-collapse: collapse; width: 100%; margin: 20px 0;">
  <tr>
    <td style="padding: 10px; border: 1px solid #ddd; background: #f8f9fa; width: 140px;">
      <strong>Tailored Resume</strong>
    </td>
    <td style="padding: 10px; border: 1px solid #ddd;">
      <a href="{resume_url}" style="color: #1a73e8;">Open in Google Drive</a>
    </td>
  </tr>{cover_letter_row}
  <tr>
    <td style="padding: 10px; border: 1px solid #ddd; background: #f8f9fa;">
      <strong>Job Posting</strong>
    </td>
    <td style="padding: 10px; border: 1px solid #ddd;">
      <a href="{job_url}" style="color: #1a73e8;">View on Indeed</a>
    </td>
  </tr>
  <tr>
    <td style="padding: 10px; border: 1px solid #ddd; background: #f8f9fa;">
      <strong>Job Tracker</strong>
    </td>
    <td style="padding: 10px; border: 1px solid #ddd;">
      <a href="{sheet_url}" style="color: #1a73e8;">Open Google Sheet</a>
    </td>
  </tr>
</table>

<p style="color: #666; font-size: 13px;">
  This resume was rewritten to mirror the language and keywords in the job description.
  All numbers, dates, and company names are unchanged from your original.
</p>

<p style="color: #999; font-size: 12px; border-top: 1px solid #eee; padding-top: 10px;">
  Sent by your JobSearchAutomation
</p>

</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = to
    msg["To"] = to
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))
    return msg


def send_resume_notification(to: str, job_title: str, company: str,
                             resume_url: str, job_url: str, sheet_url: str,
                             cover_letter_url: str = None) -> None:
    """
    Send a resume-ready notification email via Gmail API.

    Args:
        to:                Recipient address (user's own Gmail)
        job_title:         Job title
        company:           Company name
        resume_url:        Drive URL of the tailored resume
        job_url:           Indeed URL of the job posting
        sheet_url:         Google Sheets URL of the tracker
        cover_letter_url:  Drive URL of the cover letter (optional)

    Raises:
        Exception on send failure
    """
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    msg = build_email(to, job_title, company, resume_url, job_url, sheet_url, cover_letter_url)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    service.users().messages().send(
        userId="me",
        body={"raw": raw}
    ).execute()


def main():
    parser = argparse.ArgumentParser(description="Send resume-ready notification email.")
    parser.add_argument("--to", required=True)
    parser.add_argument("--job_title", required=True)
    parser.add_argument("--company", required=True)
    parser.add_argument("--resume_url", required=True)
    parser.add_argument("--cover_letter_url", default=None)
    parser.add_argument("--job_url", required=True)
    parser.add_argument("--sheet_url", required=True)
    args = parser.parse_args()

    try:
        send_resume_notification(
            to=args.to,
            job_title=args.job_title,
            company=args.company,
            resume_url=args.resume_url,
            job_url=args.job_url,
            sheet_url=args.sheet_url,
            cover_letter_url=args.cover_letter_url,
        )
        print("ok")
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
