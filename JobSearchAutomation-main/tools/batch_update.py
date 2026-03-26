"""
Helper: batch_update.py

Updates one entry in batch_content.json with resume lines and cover letter text.
Called by Claude after generating content for each job.

Usage:
    python tools/batch_update.py \
        --batch_file ".tmp/batch_content.json" \
        --sheet_row 2 \
        --resume_file ".tmp/resume_draft.txt" \
        --cover_file ".tmp/cover_draft.txt"
"""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch_file", required=True)
    parser.add_argument("--sheet_row", type=int, required=True)
    parser.add_argument("--resume_file", required=True)
    parser.add_argument("--cover_file", required=True)
    args = parser.parse_args()

    batch_path = Path(args.batch_file)
    entries = json.loads(batch_path.read_text(encoding="utf-8"))

    resume_lines = Path(args.resume_file).read_text(encoding="utf-8").splitlines()
    cover_text = Path(args.cover_file).read_text(encoding="utf-8").strip()

    updated = False
    for entry in entries:
        if entry["sheet_row"] == args.sheet_row:
            entry["resume_lines"] = resume_lines
            entry["cover_letter"] = cover_text
            entry["status"] = "content_ready"
            updated = True
            break

    if not updated:
        print(f"ERROR: sheet_row {args.sheet_row} not found in batch file", file=sys.stderr)
        sys.exit(1)

    batch_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    print(f"Updated row {args.sheet_row}")


if __name__ == "__main__":
    main()
