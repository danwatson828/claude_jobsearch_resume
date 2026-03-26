# Workflow: Process Manual Jobs

## Trigger phrases
- "process my manual jobs"
- "run manual jobs"
- "process manual jobs"
- "run the manual jobs workflow"

---

## Overview

Users paste jobs found from any source (not just LinkedIn) into a "Manual Jobs" sheet tab.
This workflow fetches each job description, tailors the resume, writes a cover letter,
and puts the Drive links back into that tab.

---

## Step 0 — Load environment

Read `GOOGLE_SHEET_ID` from `.env`. All steps below use this value.

---

## Step 1 — Read pending jobs

```
python tools/sheets.py --action get_manual_jobs --sheet_id <GOOGLE_SHEET_ID>
```

**If the command fails with a sheet-not-found or tab-not-found error:**
Run `create_manual_tab` first:
```
python tools/sheets.py --action create_manual_tab --sheet_id <GOOGLE_SHEET_ID>
```
Then inform the user: "Created the Manual Jobs tab. Add job rows (Company, Title, URL) and re-run."
Stop here — nothing to process yet.

**If result is an empty array `[]`:**
Report: "No pending manual jobs." and stop.

**Otherwise:** proceed with the returned array of job objects.
Each object has: `manual_row`, `company`, `job_title`, `url`, `location`, `salary`.

---

## Step 2 — Fetch JDs and extract metadata

For each pending job, use `WebFetch` on `url` to extract the full job description text.

- Extract all meaningful text: title, requirements, responsibilities, qualifications.
- Strip navigation, ads, and boilerplate unrelated to the job.

**On fetch error (network failure, 404, paywall, etc.):**
```
python tools/sheets.py --action update_manual_job --sheet_id <GOOGLE_SHEET_ID> \
  --row_num <manual_row> --status "Error: could not fetch JD"
```
Skip that job and continue with the rest.

**After a successful fetch, fill in any blank metadata fields:**

1. If `company` is blank in the sheet row, parse the company name from the page.
2. If `job_title` is blank, parse the job title from the page.
3. If `location` is blank, parse location if present on the page.
4. If `salary` is blank, parse salary/compensation range if present.

Write extracted fields back to the sheet immediately (before continuing to Step 3):
```
python tools/sheets.py --action update_manual_job --sheet_id <GOOGLE_SHEET_ID> \
  --row_num <manual_row> \
  --company "<extracted_or_original>" --job_title "<extracted_or_original>" \
  --location "<extracted_or_original>" --salary "<extracted_or_original>"
```

Only pass a field if it has a non-empty value (extracted or already set). Skip params
that remain blank rather than writing empty strings.

Use the resolved values (extracted or original) for all downstream steps.

---

## Step 3 — Append to main Jobs tab

For each job with a successfully fetched JD, append a row to the main Jobs tab.
Use today's date for Date Found. Leave Date Posted blank. Use `"manual"` as the Job ID
(not a hash — this avoids false deduplication collisions).

```
python tools/sheets.py --action append_row --sheet_id <GOOGLE_SHEET_ID> \
  --row '["<today>","<job_title>","<company>","<location>","<salary>","","<url>","New","","manual"]'
```

Capture the printed row number as `main_row`.

Immediately write `main_row` and status "Processing" back to the Manual Jobs tab:
```
python tools/sheets.py --action update_manual_job --sheet_id <GOOGLE_SHEET_ID> \
  --row_num <manual_row> --main_row <main_row> --status "Processing"
```

---

## Step 4 — Build batch_content.json entries

Read `.tmp/batch_content.json` if it exists (parse as JSON array); otherwise start with `[]`.

Append one entry per job:
```json
{
  "sheet_row": <main_row>,
  "company": "<company>",
  "job_title": "<job_title>",
  "job_url": "<url>",
  "jd": "<fetched jd text>",
  "resume_lines": [],
  "cover_letter": "",
  "status": "pending",
  "_manual_row": <manual_row>
}
```

`_manual_row` is only used in Step 7 to correlate results back to the Manual Jobs tab.
It is ignored by all existing pipeline scripts.

Write the updated array back to `.tmp/batch_content.json`.

---

## Step 5 — Generate tailored content

Run the batch content generator:
```
python tools/generate_batch_content.py
```

This script tailors the resume lines and writes a cover letter for each pending entry.
It applies `humanize()` internally before saving — do not skip this step.

After the script completes, verify that `status` fields in `.tmp/batch_content.json`
have been updated from `"pending"` to `"ready"` (or similar) for the manual entries.

---

## Step 6 — Upload to Drive

Run the batch tailor tool:
```
python tools/batch_tailor.py --batch_file .tmp/batch_content.json
```

This uploads the tailored resume and cover letter for each entry to Drive and writes
the resulting URLs into columns I and K of the main Jobs tab (identified by `sheet_row`).

Output is logged to `.tmp/batch_tailor_log.txt`.

---

## Step 7 — Write results back to Manual Jobs tab

Parse `.tmp/batch_tailor_log.txt` for lines like:
```
[timestamp] Row N: resume uploaded → https://...
[timestamp] Row N: cover letter uploaded → https://...
```

Cross-reference `Row N` (main Jobs tab row) against `sheet_row` in each batch entry
to find the matching `_manual_row`.

For each completed manual entry, call:
```
python tools/sheets.py --action update_manual_job --sheet_id <GOOGLE_SHEET_ID> \
  --row_num <manual_row> --status "Done" \
  --resume_url "<resume drive url>" --cover_url "<cover letter drive url>"
```

For any manual entry whose `sheet_row` does not appear in the log (upload failed):
```
python tools/sheets.py --action update_manual_job --sheet_id <GOOGLE_SHEET_ID> \
  --row_num <manual_row> --status "Error: upload failed"
```

---

## Step 8 — Report

Print a summary:
- Number of jobs processed successfully (status "Done")
- Number of errors, with brief reason for each
- Main Jobs tab row numbers that were added

Example:
```
Manual jobs processed: 2 done, 1 error
  Row 14: Acme Corp — Security Engineer (Done)
  Row 15: Beta Inc — Staff Engineer (Done)
  Row 16: Gamma LLC — Error: could not fetch JD
```

---

## Notes

- Manual jobs flow through the same pipeline as LinkedIn jobs — `batch_tailor.py` is
  reused unchanged. The only difference is that manual jobs have `"manual"` in the
  Job ID column (J) instead of a hash.
- Rows already marked "Processing", "Done", or "Error" in column G are never returned
  by `get_manual_jobs` and will not be processed again.
- To re-process a failed row, clear column G in the Manual Jobs tab and re-run.
