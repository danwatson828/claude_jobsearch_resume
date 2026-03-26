"""
Tool: search_indeed.py

Purpose:
    Parameter parsing, result normalization, date filtering, and .tmp/ backup
    for Indeed job searches. The agent calls Indeed MCP tools directly and
    passes results here for processing.

Usage:
    python tools/search_indeed.py \
        --titles "Software Engineer, Backend Developer" \
        --location "Austin, TX" \
        --salary_min 80000 \
        --keywords "include:python,sql exclude:unpaid,internship" \
        --since_date "2026-03-07"

Parameters:
    --titles      Comma-separated list of job titles to search
    --location    City/state string or "Remote"
    --salary_min  Integer minimum salary (0 = no filter)
    --keywords    Raw keyword string from .env (format: "include:a,b exclude:c,d")
    --since_date  ISO date string YYYY-MM-DD. Only return jobs posted on or after
                  this date. Omit (or pass empty string) to return all results —
                  used on first run when no LAST_SEARCH_DATE exists yet.

Returns:
    JSON array printed to stdout. Each object:
    {
        "title": str,
        "company": str,
        "location": str,
        "salary": str,       # May be empty string if not listed
        "date_posted": str,  # As returned by Indeed (e.g. "2 days ago", "2026-03-07")
        "url": str,          # Direct link to job posting
        "description": str   # Full job description text
    }

Exit codes:
    0 = success (even if 0 results after filtering)
    1 = error (details printed to stderr)

Notes:
    - The agent calls mcp__claude_ai_Indeed__search_jobs and get_job_details directly.
      This script handles everything after those calls: parsing, filtering, and backup.
    - Date filtering is applied BEFORE deduplication in the workflow. If a date cannot
      be parsed, the job is included (fail open — never silently drop a real job).
    - Results are written to .tmp/search_results_<timestamp>.json before filtering,
      and .tmp/search_results_<timestamp>_filtered.json after, for debugging.
"""

import argparse
import json
import re
import sys
import os
from datetime import date, datetime, timedelta


# ---------------------------------------------------------------------------
# Keyword parsing
# ---------------------------------------------------------------------------

def parse_keywords(raw: str) -> dict:
    """
    Parse the raw KEYWORDS string from .env into include/exclude lists.

    Args:
        raw: String like "include:python,sql exclude:unpaid,internship"

    Returns:
        {"include": ["python", "sql"], "exclude": ["unpaid", "internship"]}
    """
    result = {"include": [], "exclude": []}
    if not raw:
        return result
    for part in raw.strip().split():
        if part.startswith("include:"):
            result["include"] = [k.strip() for k in part[8:].split(",") if k.strip()]
        elif part.startswith("exclude:"):
            result["exclude"] = [k.strip() for k in part[8:].split(",") if k.strip()]
    return result


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def parse_date_posted(date_str: str) -> date | None:
    """
    Parse a date_posted string returned by Indeed into a datetime.date.

    Indeed returns posting dates in several formats:
        "Just posted"       → today
        "Today"             → today
        "1 day ago"         → yesterday
        "3 days ago"        → 3 days before today
        "30+ days ago"      → 30 days before today (treat the number conservatively)
        "2026-03-07"        → ISO date, parsed directly
        "March 7, 2026"     → long-form date string

    If the string cannot be parsed, returns None. Callers should treat None
    as "include this job" — never silently drop a result due to a parse failure.

    Args:
        date_str: Raw date string from Indeed job object

    Returns:
        datetime.date or None if unparseable
    """
    if not date_str:
        return None

    today = date.today()
    s = date_str.strip().lower()

    # "just posted" / "today" / "active today"
    if s in ("just posted", "today", "active today", "posted today"):
        return today

    # "yesterday"
    if s == "yesterday":
        return today - timedelta(days=1)

    # "X day ago" / "X days ago" / "30+ days ago"
    match = re.match(r"(\d+)\+?\s+days?\s+ago", s)
    if match:
        return today - timedelta(days=int(match.group(1)))

    # "1 day ago"
    match = re.match(r"(\d+)\+?\s+day\s+ago", s)
    if match:
        return today - timedelta(days=int(match.group(1)))

    # ISO format: "2026-03-07"
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        pass

    # Long form: "March 7, 2026"
    try:
        return datetime.strptime(date_str.strip(), "%B %d, %Y").date()
    except ValueError:
        pass

    # Short form: "Mar 7, 2026"
    try:
        return datetime.strptime(date_str.strip(), "%b %d, %Y").date()
    except ValueError:
        pass

    # Unparseable — return None so caller includes the job
    return None


# ---------------------------------------------------------------------------
# Date filtering
# ---------------------------------------------------------------------------

def filter_by_date(results: list, since_date_str: str) -> tuple[list, int]:
    """
    Filter job results to only those posted on or after since_date.

    Jobs with unparseable dates are always included (fail open).
    Jobs with a parsed date before since_date are excluded.

    Args:
        results:        List of job dicts from Indeed
        since_date_str: ISO date string "YYYY-MM-DD", or empty string to skip filtering

    Returns:
        Tuple of (filtered_list, skipped_count)
        - filtered_list: jobs that passed the filter
        - skipped_count: number of jobs excluded as already-seen
    """
    if not since_date_str or not since_date_str.strip():
        return results, 0

    try:
        since = datetime.strptime(since_date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        # Malformed since_date — skip filtering entirely rather than drop everything
        return results, 0

    kept = []
    skipped = 0
    for job in results:
        posted = parse_date_posted(job.get("date_posted", ""))
        if posted is None:
            # Can't parse date — include the job
            kept.append(job)
        elif posted >= since:
            kept.append(job)
        else:
            skipped += 1

    return kept, skipped


# ---------------------------------------------------------------------------
# .tmp/ backup
# ---------------------------------------------------------------------------

def save_to_tmp(results: list, suffix: str = "") -> str:
    """
    Save search results to .tmp/ as a timestamped JSON backup.

    Args:
        results: List of job dicts
        suffix:  Optional filename suffix (e.g. "_filtered")

    Returns:
        File path of the saved backup
    """
    os.makedirs(".tmp", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f".tmp/search_results_{timestamp}{suffix}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Filter and save Indeed search results.")
    parser.add_argument("--titles", required=True, help="Comma-separated job titles")
    parser.add_argument("--location", required=True, help="Location or 'Remote'")
    parser.add_argument("--salary_min", type=int, default=0, help="Minimum salary")
    parser.add_argument("--keywords", default="", help="include:/exclude: keyword string")
    parser.add_argument("--since_date", default="",
                        help="ISO date YYYY-MM-DD — only return jobs posted on or after this date. "
                             "Omit on first run to return all results.")
    parser.add_argument("--results_file", default="",
                        help="Path to a JSON file containing raw results from the agent. "
                             "When provided, reads from file instead of stdin.")
    args = parser.parse_args()

    try:
        # Read raw results — either from a file the agent wrote, or from stdin
        if args.results_file:
            with open(args.results_file, encoding="utf-8") as f:
                raw_results = json.load(f)
        else:
            raw_results = json.load(sys.stdin)

        # Save raw backup
        save_to_tmp(raw_results)

        # Apply date filter
        filtered, skipped = filter_by_date(raw_results, args.since_date)

        # Save filtered backup
        save_to_tmp(filtered, suffix="_filtered")

        # Print summary to stderr for agent visibility
        print(
            f"# Results: {len(raw_results)} total, {skipped} skipped (already seen), "
            f"{len(filtered)} new",
            file=sys.stderr
        )

        print(json.dumps(filtered, indent=2, ensure_ascii=False))
        sys.exit(0)

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
