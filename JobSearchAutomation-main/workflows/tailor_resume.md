# Workflow: Tailor Resume

## Objective
Rewrite the user's resume to mirror the language, keywords, and priorities of a specific job description. The output is a new .docx built from the original resume as a template — preserving all fonts, sizes, spacing, bold, colors, and layout exactly. The URL is written back into the job tracker sheet.

## When This Runs
- Called automatically by `workflows/search_jobs.md` for each new job added to the sheet.
- Never runs standalone unless manually triggered for a specific job.

## Inputs (passed in from search_jobs)
- `job_url` — direct link to the job posting
- `job_description` — full text of the job description
- `company` — company name
- `job_title` — job title
- `sheet_row` — row number in the Google Sheet to write the result back to

---

## Step 0: Resume–Role Fit Check

Before doing any work, compare the resume (from `RESUME_DRIVE_URL` in `.env`) against the `job_title` and `job_description` inputs.

Look for obvious mismatch signals — the same signals used during onboarding:
- The recent experience is in a different function or career track than the target role
- The resume lacks most of the core skills, tools, or domain language implied by the role
- The resume would require heavy reframing rather than normal tailoring

**If the mismatch is obvious:**

Stop. Do not proceed. Tell the user:

> "The resume on file looks significantly misaligned with the role being applied to ([job_title] at [company]). Tailoring it is likely to produce a weak result and would waste compute. Would you like to replace the resume first, or proceed anyway?"

Wait for a response before continuing.

- **User says replace:** Ask them to drop the new resume into the `resume/` folder and type 'done'. Then re-run onboarding Step 4 (Resume Review and Upload), and resume tailoring with the new file.
- **User says proceed anyway:** Continue to Step 1.

**If the fit is reasonable or ambiguous:** Continue to Step 1 silently.

This check applies even when called from `search_jobs.md` mid-run. If you notice the resume is mismatched for the first job, pause the entire batch and ask — do not tailor any jobs until the user responds.

---

## Step 1: Load Resume Structure

Run:
```
python tools/tailor_resume.py --action read_resume_structured
```

This reads the original .docx and returns every paragraph numbered and tagged:
```
1|[HEADER] Jordan Lee
2|[NORMAL] City, State | 000-000-0000 | candidate@example.com
3|[EMPTY]
4|[HEADER] PROFESSIONAL SUMMARY
5|[NORMAL] Experienced lease accounting manager with 8 years...
6|[HEADER] EXPERIENCE
7|[ROLE] Accounting Manager | Acme Corp | 2019–Present
8|[BULLET] Managed portfolio of 30 leases totaling $100K monthly rents
9|[BULLET] Reduced close cycle from 10 days to 6 through process automation
10|[EMPTY]
11|[ROLE] Staff Accountant | Prior Corp | 2016–2019
12|[BULLET] Prepared monthly financial statements
```

Tag meanings:
- `[HEADER]` — section heading (e.g. "EXPERIENCE", "EDUCATION") or name line — rewrite lightly or leave as-is
- `[ROLE]` — job title / company / date line — this is a **section boundary anchor**; never move or reorder these lines
- `[NORMAL]` — body paragraph that is NOT a role anchor — rewrite to match job language
- `[BULLET]` — list item — rewrite, lead with a strong action verb
- `[EMPTY]` — blank spacer line — return exactly as `N|[EMPTY]`, never change

**If the tool does not distinguish [ROLE] from [NORMAL]:** Identify [ROLE] lines yourself.
A line is a `[ROLE]` if it immediately follows a `[HEADER]` or `[EMPTY]` line and contains a job title,
company name, and/or date range. Treat it as `[ROLE]` in your working copy regardless of what the tool tagged it.

**If the tool returns a .doc error:** Run `python tools/tailor_resume.py --action convert_to_docx` first, then retry.

If it fails for any other reason, log the error and skip this job.

---

## Step 2: Analyze the Job Description

Using the `job_description` text, identify:

1. **Required skills** — technologies, tools, certifications mentioned as required or preferred
2. **Key responsibilities** — the top 5–7 action-verb phrases describing what the role does
3. **Tone and language style** — formal vs. casual, technical depth, industry jargon
4. **Priority signals** — words that appear repeatedly or appear in the first paragraph

This analysis is done directly by the agent — no tool call needed.

---

## Step 2.5: Load Bullet Library and Select Bullets

Read `resume/bullets.md` in full.

For each role section, select the bullets that best match the job's key responsibilities and language from Step 2. Match the number of bullets to the number of lines available in that role's section. Log your selections before writing anything:

```
Selected: AVP=[AVP-XX, AVP-XX, ...]  RD=[RD-XX, ...]  PH=[PH-XX, ...]  Summary=[SUM-XX]
```

Rules:
- Select only from the pool for that role — do not pull bullets across sections
- Match count to the number of lines in that role's section (e.g., 6 lines = 6 bullets)

---

## Step 3: Rewrite the Resume

Before writing a single line, build a **section map** from the numbered paragraph list:

```
Section map (example):
  Lines 1–5:   Header / contact / summary (no [ROLE] anchor — global scope)
  Lines 6–6:   [HEADER] EXPERIENCE
  Lines 7–15:  ROLE → "Accounting Manager | Acme Corp | 2019–Present"
  Lines 16–25: ROLE → "Staff Accountant | Prior Corp | 2016–2019"
  Lines 26–26: [HEADER] EDUCATION
  Lines 27–29: Education content
```

Write out this map before rewriting. It is your structural contract — every bullet you move,
rewrite, or reorder must stay within its assigned section's line range.

Now produce a rewritten version in the **exact same format** — same paragraph numbers, same tags, same total count.

**For bullets ([NORMAL] and [BULLET] in experience sections):**

Start from the bullet selected in Step 2.5. Reframe the language to mirror the JD vocabulary — swap action verbs, replace generic terms with job-specific ones, adjust framing — but do not change the accomplishment itself. Every number, dollar amount, percentage, company name, and product name must appear verbatim.

**Not allowed:** change what was built, saved, reduced, or achieved; add tools or domains not in the source bullet; use a bullet not selected in Step 2.5.

**For the summary (line 4):**
Start from the summary selected in Step 2.5. May open with the target job title. Must preserve all facts verbatim. Do not rewrite from scratch.

**For skills section (lines 40–44):** Update domain vocabulary freely to match job language. No locked facts. No fabrication.

**For all other line types ([EMPTY], [ROLE], [HEADER]):**
- Return every [EMPTY] line unchanged: `N|[EMPTY]`
- Return every [ROLE] line with its paragraph number and tag preserved exactly — only light rewording of the title itself is allowed
- Do not move any content across a [ROLE] boundary
- Do not reorder [ROLE] lines — role order must match the original exactly
- Do not change paragraph count — the output must have the same number of lines as the input

**Example output:**
```
1|[HEADER] Jordan Lee
2|[NORMAL] City, State | 000-000-0000 | candidate@example.com
3|[EMPTY]
4|[HEADER] PROFESSIONAL SUMMARY
5|[NORMAL] Lease accounting specialist with 8 years driving compliance and efficiency...
6|[HEADER] EXPERIENCE
7|[ROLE] Accounting Manager | Acme Corp | 2019–Present
8|[BULLET] Oversaw portfolio of 30 commercial leases generating $100K in monthly rents
9|[BULLET] Accelerated close cycle from 10 to 6 days through targeted process automation
10|[EMPTY]
11|[ROLE] Staff Accountant | Prior Corp | 2016–2019
12|[BULLET] Prepared monthly financial statements
```

---

## Step 3.5: Verify Section Integrity Before Saving

Before writing anything to disk, run this checklist against your rewritten paragraph list.
If any check fails, fix the output and re-run the checklist — do not proceed until all pass.

**Check 1 — Paragraph count matches**
Count the lines in your rewrite. It must equal the count from Step 1.
If it doesn't: find the missing or extra line and correct it.

**Check 2 — [ROLE] anchors are in the same positions**
For each [ROLE] line in the original, confirm it appears at the same paragraph number in your rewrite.
If a [ROLE] line has shifted: something was inserted or deleted above it. Find and fix it.

**Check 3 — No content has crossed a role boundary**
For each role section (the lines between one [ROLE] anchor and the next), confirm that all bullet
content in your rewrite was present in the same section in the original.
Concretely: pick 2–3 bullets from each role in your rewrite and verify they appear
in the corresponding role in the original.
If a bullet appears under the wrong role: move it back to its correct section.

**Check 4 — [EMPTY] lines are unchanged**
Every line tagged [EMPTY] in the original must appear at the same number and be unchanged.

**Check 5 — All bullets trace to the library**

For each experience bullet in your output, confirm it originated from a bullet in `resume/bullets.md` for that role section and that all numbers, dollar amounts, and percentages from the source bullet appear verbatim.

If any bullet fails: rewrite it using the correct library entry before proceeding.

Append the selection log from Step 2.5 to `.tmp/tailor_resume_log.txt` with timestamp and job URL.

**If all 5 checks pass:** log "Section integrity verified." and continue to Step 4.
**If any check fails:** fix the output, log what was wrong and what you corrected, and re-run all 5 checks.

---

## Step 4: Save Rewritten Content to File

**Do NOT pass resume content as a command-line argument.** The shell corrupts special characters — `$100K` becomes `00K`, `50%` disappears. Always write to a file first.

Use the Write tool to save the rewritten paragraph list to:
```
.tmp/resume_<Company>_<JobTitle>.txt
```

---

## Step 5: Build and Upload Tailored Resume

Run:
```
python tools/tailor_resume.py --action create_doc_from_template \
  --company "<company>" \
  --job_title "<job_title>" \
  --content_file ".tmp/resume_<Company>_<JobTitle>.txt"
```

The tool:
1. Copies the original .docx as a template
2. Walks every paragraph and replaces text with the rewritten version
3. Preserves all original formatting — fonts, sizes, bold, italic, colors, spacing, indentation
4. Saves the result to `.tmp/` and uploads to the "Tailored Resumes" folder in Google Drive
5. Returns the shareable Drive URL

---

## Step 5.5: Write Cover Letter

Using the JD analysis from Step 2 and the bullet selections from Step 2.5, write a cover letter.

**Format:** 3 paragraphs, plain text, no salutation or closing (the tool adds those).

**Paragraph 1 — Opening:** Express genuine interest in the role and company. Connect the role to what you find compelling about the problem space or the company's work. Tone: friendly, specific, not generic.

**Paragraph 2 — Fit:** Briefly convey why the background is relevant. Draw on the narrative arc of the experience — healthcare analytics, building teams and practices, translating data into decisions — without citing specific numbers. Match the vocabulary and priorities of the JD.

**Paragraph 3 — Close:** Express enthusiasm for the conversation. Keep it short and direct.

**Rules:**
- Do not invent facts, credentials, or experiences not present in `resume/bullets.md` or the resume
- Do not contradict any number, company name, or accomplishment in the bullet library
- Keep it to 3 paragraphs — do not pad
- Friendly and excited, not formal or stiff

Save the letter body (paragraphs only, separated by blank lines) to:
```
.tmp/cover_<Company>_<JobTitle>.txt
```

Then run:
```
python tools/cover_letter.py \
  --company "<company>" \
  --job_title "<job_title>" \
  --content_file ".tmp/cover_<Company>_<JobTitle>.txt"
```

The tool formats it as a .docx, uploads to the "Cover Letters" folder in Google Drive, and returns a shareable URL.

---

## Step 6: Write URLs Back to Sheet

Run `python tools/sheets.py --action update_notes` with:
- `--sheet_id` = `GOOGLE_SHEET_ID` (from `.env`)
- `--row_num` = the `sheet_row` input
- `--notes` = the Drive URL from Step 5

Then run `python tools/sheets.py --action update_cover_letter` with:
- `--sheet_id` = `GOOGLE_SHEET_ID` (from `.env`)
- `--row_num` = the `sheet_row` input
- `--notes` = the Drive URL from Step 5.5

---

## Step 7: Send Email Notification

Read `USER_EMAIL` and `GOOGLE_SHEET_ID` from `.env`.

Run:
```
python tools/notify.py \
  --to "<USER_EMAIL>" \
  --job_title "<job_title>" \
  --company "<company>" \
  --resume_url "<drive_url_from_step_5>" \
  --cover_letter_url "<drive_url_from_step_5.5>" \
  --job_url "<job_url>" \
  --sheet_url "https://docs.google.com/spreadsheets/d/<GOOGLE_SHEET_ID>"
```

- If it succeeds: continue silently.
- If it fails: log the error to `.tmp/tailor_resume_log.txt` but do NOT block — the resume
  was already saved and the sheet was already updated. Notification failure is non-fatal.

---

## Step 8: Return Result

Return the Drive URL to the calling workflow (`search_jobs.md`).

---

## Error Handling

| Error | Action |
|---|---|
| .doc file detected | Run `convert_to_docx` action first, then retry |
| Resume not found | Log error, skip this job |
| Job description blank | Log warning, attempt rewrite with job title only |
| Paragraph count mismatch after rewrite | Fix rewrite before proceeding — never save a misaligned result |
| [ROLE] anchor shifted in rewrite | Fix rewrite — move displaced content back to its correct section |
| Content crossed role boundary | Fix rewrite — return content to the role it originated from |
| Bullet not in library | Rewrite using a library entry before saving |
| Upload fails | Log error, return None — Notes column stays blank |
| Cover letter upload fails | Log error, continue — resume is already saved; cover letter column stays blank |
| Sheet update fails | Log error, still return the Drive URL |
| Notification fails | Log error, continue — resume and sheet are already saved |

All errors logged to `.tmp/tailor_resume_log.txt` with timestamp and job URL.

---

## Quality Constraints

- Every number, dollar amount, date, and company name in the tailored resume must match the source exactly
- Do not pad the resume — if the original is one page, the output should be one page
- The rewrite is traceable: every line in the output must be derivable from a line in the original

---

## Tools Used
- `tools/tailor_resume.py` — reads resume structure, applies rewrite to template, uploads to Drive
- `tools/cover_letter.py` — formats cover letter as .docx, uploads to Drive "Cover Letters" folder
- `tools/sheets.py` — writes resume URL to column I, cover letter URL to column K
- `tools/notify.py` — sends email notification with resume, cover letter, and job links
- `tools/google_auth.py` — provides authenticated credentials
