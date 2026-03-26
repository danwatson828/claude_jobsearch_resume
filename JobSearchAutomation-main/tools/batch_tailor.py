"""
Tool: batch_tailor.py

Purpose:
    Process a batch of pre-generated resume and cover letter content.
    Reads a JSON file of jobs with content already written by Claude,
    then handles all mechanical work: file creation, docx building,
    Drive uploads, sheet updates, and email notifications.

    This separates content generation (Claude's job) from execution (this script's job).

Usage:
    python tools/batch_tailor.py --batch_file ".tmp/batch_content.json" [--dry_run]

Batch file format (.tmp/batch_content.json):
    [
      {
        "sheet_row": 2,
        "company": "Acme Corp",
        "job_title": "VP Analytics",
        "job_url": "https://...",
        "resume_lines": [
          "1|[HEADER] YOUR NAME",
          "2|[NORMAL] phone · email · linkedin",
          ...
        ],
        "cover_letter": "Paragraph one text.\\n\\nParagraph two text.\\n\\nParagraph three text.",
        "status": "pending"   <- updated to "done" or "error" as processed
      },
      ...
    ]

Parameters:
    --batch_file   Path to the JSON batch file
    --dry_run      If set, print what would happen without making any API calls

Behavior:
    - Skips entries where status == "done"
    - Processes pending entries in order
    - Updates status in place after each entry (safe to re-run after interruption)
    - Logs all activity to .tmp/batch_tailor_log.txt

Exit codes:
    0 = all entries processed (some may have errored — check log)
    1 = could not read batch file or fatal error
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

TMP = Path(__file__).parent.parent / ".tmp"
ENV_PATH = Path(__file__).parent.parent / ".env"
LOG_PATH = TMP / "batch_tailor_log.txt"


def _load_env() -> dict:
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def process_entry(entry: dict, env: dict, dry_run: bool) -> str:
    """
    Process one job entry. Returns "done" or "error:<msg>".
    """
    row = entry["sheet_row"]
    company = entry["company"]
    job_title = entry["job_title"]
    job_url = entry.get("job_url", "")
    resume_lines = entry["resume_lines"]
    cover_text = entry.get("cover_letter", "")

    sheet_id = env.get("GOOGLE_SHEET_ID", "")
    user_email = env.get("USER_EMAIL", "")

    import re
    def safe(text):
        return re.sub(r"[^\w\s-]", "", text).strip().replace(" ", "_")

    resume_file = TMP / f"resume_{safe(company)}_{safe(job_title)}.txt"
    cover_file = TMP / f"cover_{safe(company)}_{safe(job_title)}.txt"

    try:
        # --- Save resume content ---
        resume_content = "\n".join(resume_lines)
        if not dry_run:
            resume_file.write_text(resume_content, encoding="utf-8")
        log(f"Row {row}: saved resume content → {resume_file.name}")

        # --- Build and upload resume docx ---
        cmd = (
            f'python tools/tailor_resume.py --action create_doc_from_template '
            f'--company "{company}" --job_title "{job_title}" '
            f'--content_file "{resume_file}"'
        )
        if dry_run:
            log(f"Row {row}: [DRY RUN] would run: {cmd}")
            resume_url = "https://drive.google.com/dry-run-resume"
        else:
            import subprocess
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"tailor_resume failed: {result.stderr.strip()}")
            resume_url = result.stdout.strip()
            log(f"Row {row}: resume uploaded → {resume_url}")

        # --- Save cover letter content ---
        if cover_text:
            if not dry_run:
                cover_file.write_text(cover_text, encoding="utf-8")
            log(f"Row {row}: saved cover letter content → {cover_file.name}")

            cmd_cl = (
                f'python tools/cover_letter.py '
                f'--company "{company}" --job_title "{job_title}" '
                f'--content_file "{cover_file}"'
            )
            if dry_run:
                log(f"Row {row}: [DRY RUN] would run: {cmd_cl}")
                cover_url = "https://drive.google.com/dry-run-cover"
            else:
                result_cl = subprocess.run(cmd_cl, shell=True, capture_output=True, text=True)
                if result_cl.returncode != 0:
                    log(f"Row {row}: cover letter upload failed: {result_cl.stderr.strip()} — continuing")
                    cover_url = ""
                else:
                    cover_url = result_cl.stdout.strip()
                    log(f"Row {row}: cover letter uploaded → {cover_url}")
        else:
            cover_url = ""

        # --- Update sheet ---
        if sheet_id and not dry_run:
            import subprocess

            r1 = subprocess.run(
                f'python tools/sheets.py --action update_notes '
                f'--sheet_id "{sheet_id}" --row_num {row} --notes "{resume_url}"',
                shell=True, capture_output=True, text=True
            )
            if r1.returncode != 0:
                log(f"Row {row}: sheet notes update failed: {r1.stderr.strip()}")
            else:
                log(f"Row {row}: sheet notes updated")

            if cover_url:
                r2 = subprocess.run(
                    f'python tools/sheets.py --action update_cover_letter '
                    f'--sheet_id "{sheet_id}" --row_num {row} --notes "{cover_url}"',
                    shell=True, capture_output=True, text=True
                )
                if r2.returncode != 0:
                    log(f"Row {row}: cover letter column update failed: {r2.stderr.strip()}")
                else:
                    log(f"Row {row}: cover letter column updated")
        elif dry_run:
            log(f"Row {row}: [DRY RUN] would update sheet row {row}")

        # --- Send email notification ---
        if user_email and sheet_id and not dry_run:
            sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"
            cl_arg = f'--cover_letter_url "{cover_url}"' if cover_url else ""
            job_arg = f'--job_url "{job_url}"' if job_url else f'--job_url "{sheet_url}"'
            cmd_email = (
                f'python tools/notify.py --to "{user_email}" '
                f'--job_title "{job_title}" --company "{company}" '
                f'--resume_url "{resume_url}" {cl_arg} '
                f'{job_arg} --sheet_url "{sheet_url}"'
            )
            try:
                r3 = subprocess.run(cmd_email, shell=True, capture_output=True, text=True)
                if r3.returncode != 0:
                    log(f"Row {row}: email failed (non-fatal): {r3.stderr.strip()}")
                else:
                    log(f"Row {row}: email sent")
            except Exception as email_exc:
                log(f"Row {row}: email exception (non-fatal): {email_exc}")

        return "done"

    except Exception as e:
        log(f"Row {row}: ERROR — {e}")
        return f"error:{e}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch_file", required=True)
    parser.add_argument("--dry_run", action="store_true")
    args = parser.parse_args()

    batch_path = Path(args.batch_file)
    if not batch_path.exists():
        print(f"ERROR: batch file not found: {batch_path}", file=sys.stderr)
        sys.exit(1)

    env = _load_env()
    entries = json.loads(batch_path.read_text(encoding="utf-8"))

    pending = [e for e in entries if e.get("status") != "done"]
    log(f"Batch start: {len(entries)} total, {len(pending)} pending, dry_run={args.dry_run}")

    for i, entry in enumerate(entries):
        if entry.get("status") == "done":
            continue
        if not entry.get("resume_lines"):
            continue  # content not generated yet — skip silently
        row = entry.get("sheet_row", "?")
        company = entry.get("company", "?")
        log(f"Processing {i+1}/{len(entries)}: Row {row} — {company}")

        status = process_entry(entry, env, args.dry_run)
        entry["status"] = status

        # Write progress after each entry so we can resume if interrupted
        if not args.dry_run:
            batch_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    done = sum(1 for e in entries if e.get("status") == "done")
    errors = sum(1 for e in entries if str(e.get("status", "")).startswith("error"))
    log(f"Batch complete: {done} done, {errors} errors")


if __name__ == "__main__":
    main()
