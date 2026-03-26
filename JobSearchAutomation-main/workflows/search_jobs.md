# Workflow: Search Jobs

## Objective
Search LinkedIn for new jobs matching stored criteria, append only new results to the master Google Sheet, and trigger resume tailoring for each new job using the batch content pipeline.

## When This Runs
- On the registered schedule (set during onboarding).
- Can also be triggered manually by running `run.md`.
- **Never asks the user anything during execution.**

---

## Step 1: Load Configuration

Read `.env` and extract:
- `JOB_TITLES` - split by comma into a list
- `LOCATION`
- `SALARY_MIN`
- `KEYWORDS`
- `GOOGLE_SHEET_ID`
- `RESUME_DRIVE_URL`
- `LAST_SEARCH_DATE` - ISO date string `YYYY-MM-DD` (may be empty on first run - that is expected)

If any required field other than `LAST_SEARCH_DATE` is missing, log an error and exit. Do not ask the user - the schedule should not block on input.

---

## Step 2: Search LinkedIn

**LinkedIn is the search source.** Indeed WebFetch returns 403. Do NOT attempt the Indeed MCP connector.

Use the `WebFetch` tool to query LinkedIn job search pages directly. The LinkedIn public search URL format:

```
https://www.linkedin.com/jobs/search/?keywords=<URL-encoded+query>&location=United+States&f_TPR=r604800&f_WT=2&sortBy=DD
```

Parameters:
- `f_TPR=r604800` = jobs posted in last 7 days
- `f_WT=2` = remote only (omit for all work types)
- `sortBy=DD` = sort by date descending

**2a. Run multiple parallel searches** targeting both target titles AND fun/interesting companies.

Do not limit searches to healthcare and tech. Explicitly search for:

| Search type | Example keywords |
|---|---|
| Core titles | `Director+Analytics OR VP+Analytics OR Senior+Director+Analytics` |
| Sports & media | `Director+Analytics+sports OR Director+Analytics+media OR Director+Analytics+entertainment` |
| Fun/consumer companies | `Director+Analytics+gaming OR Director+Analytics+consumer+brand OR Director+Analytics+lifestyle` |
| Specific fun companies | Search LinkedIn for analytics director roles at DraftKings, FanDuel, ESPN, The Athletic, Disney, Spotify, Duolingo, Fanatics, Nike, Peloton, etc. |

Run at least 4-6 parallel searches per daily run to ensure broad coverage.

**2b. Fetch full job descriptions** for candidates that look relevant. Use `WebFetch` on the LinkedIn job detail page:

```
https://www.linkedin.com/jobs/view/<job_id>
```

**2c. Triage candidates.** Include a job if:
- Title is Director, Senior Director, VP, or Head of Analytics/Data/Insights
- **Exception:** Manager or Senior Manager titles at large, well-known fun companies (sports, gaming, media, entertainment, consumer brands) are acceptable if salary ≥ $180,000
- Salary ≥ $160,000 (if listed); ≥ $180,000 for manager-level roles at fun companies
- Remote or hybrid (prefer remote)
- Company and role are a reasonable fit for the user's background based on `.env` criteria

Skip: onsite-only roles outside the configured locations, manager or individual contributor roles (unless fun company + salary ≥ $180K per above), engineering-heavy platform/infrastructure roles where analytics is secondary.

---

## Step 3: Deduplicate Against Existing Sheet

Run `tools/sheets.py --action get_job_hashes --sheet_id <GOOGLE_SHEET_ID>`.

The tool returns the set of job hashes already stored in the sheet (column J).

Filter the results from Step 2: keep only jobs whose LinkedIn job ID is NOT already in that set.

LinkedIn job IDs are the numeric ID in the URL: `https://www.linkedin.com/jobs/view/4388389462` → job hash = `4388389462`.

- If 0 new jobs remain after filtering, log `"No new jobs this run."` and stop.

---

## Step 4: For Each New Job

For each new job in the filtered list:

**4a. Append to Sheet**

Run `tools/sheets.py --action append_row` with:
- `sheet_id` = `GOOGLE_SHEET_ID`
- `row` = `[today's date, title, company, location, salary, date_posted, url, "New", "", job_hash]`

Column order in sheet: `Date Found | Job Title | Company | Location | Salary | Date Posted | URL | Status | Notes | Job ID`

The tool returns the row number of the newly added row.

**4b. Add JD to batch_content.json**

Append a new entry to `.tmp/batch_content.json` with:
```json
{
  "sheet_row": <row number from 4a>,
  "company": "<company>",
  "job_title": "<job title>",
  "job_url": "<linkedin url>",
  "jd": "<full job description text>",
  "resume_lines": [],
  "cover_letter": "",
  "status": "pending"
}
```

**4c. After all new jobs are appended**, run:

```
python tools/generate_batch_content.py
```

This populates `resume_lines` and `cover_letter` for all pending entries using the canonical bullet library in `resume/bullets.md`.

**4d. Then run batch_tailor.py** to create Drive docs, update the sheet, and send notifications:

```
python tools/batch_tailor.py --batch_file .tmp/batch_content.json > .tmp/batch_run_<date>.log 2>&1 &
```

Run in background. Check the log file for results. Each new entry will have its resume and cover letter uploaded and sheet columns I and K updated.

**Note:** Email notifications via Gmail API require the Gmail API to be enabled in your GCP project. Until enabled, email steps will fail non-fatally — Drive uploads and sheet updates still complete successfully.

---

## Step 5: Record Search Date

Write today's date to `.env` as `LAST_SEARCH_DATE`:

```text
python tools/onboarding.py --action write_env --key LAST_SEARCH_DATE --value "<today's date as YYYY-MM-DD>"
```

Do this before the workflow ends so the date is saved even if a later step fails.
On the next run, `search_indeed.py` will use this date to filter out anything already seen.

---

## Error Handling

| Error | Action |
|---|---|
| `.env` missing fields | Log error, exit silently |
| `LAST_SEARCH_DATE` missing | First run — search last 7 days |
| LinkedIn WebFetch returns no results | Retry with different keyword combinations |
| Writing `LAST_SEARCH_DATE` fails | Log error, continue — job hash dedup prevents duplicates on next run |
| Sheet append fails | Log error, skip resume tailoring for that job |
| `generate_batch_content.py` fails | Check `.tmp/batch_content.json` for malformed entries |
| `batch_tailor.py` entry errors | Check `.tmp/batch_tailor_log.txt`; re-run — already-done entries are skipped |
| Email notification fails 403 | Non-fatal — Gmail API not enabled in GCP; Drive upload and sheet update still complete |

All errors are logged to `.tmp/search_jobs_log.txt` with timestamp.

---

## Tools Used
- `tools/sheets.py` - reads/writes Google Sheet via Python Google API
- `tools/generate_batch_content.py` - generates 44-line resume and cover letter content from canonical bullet library
- `tools/batch_tailor.py` - builds Drive docs, uploads, updates sheet, sends email notifications
- `resume/bullets.md` - canonical bullet library (source of truth for resume content)
