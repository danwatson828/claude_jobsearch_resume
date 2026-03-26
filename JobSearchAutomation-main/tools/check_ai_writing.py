"""
check_ai_writing.py — AI-writing quality checker

Usage:
  python tools/check_ai_writing.py <file>          check a specific .txt file
  python tools/check_ai_writing.py --all            check all .tmp/*.txt files
  python tools/check_ai_writing.py --recent [N]   check .tmp/*.txt modified in last N seconds (default 120)
  python tools/check_ai_writing.py --hook          read PostToolUse JSON from stdin, auto-detect files
"""

import json
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Import _AI_TELLS from generate_batch_content if available
# ---------------------------------------------------------------------------
_BASE_TELLS: list[tuple[str, str]] = []
try:
    sys.path.insert(0, str(Path(__file__).parent))
    from generate_batch_content import _AI_TELLS as _BASE_TELLS  # type: ignore
except Exception:
    pass

# ---------------------------------------------------------------------------
# Supplemental AI-tell phrases (soft warns)
# ---------------------------------------------------------------------------
_SUPPLEMENTAL_TELLS = [
    "leverage",
    "utilize",
    "robust",
    "cutting-edge",
    "innovative solution",
    "transformative",
    "seamlessly",
    "it's worth noting",
    "it is worth noting",
    "in conclusion",
    "to summarize",
    "I hope this",
    "feel free to",
    "certainly!",
    "absolutely!",
    "of course!",
    "as per your",
    "needless to say",
    "in today's",
    "fast-paced",
    "dynamic landscape",
    "ever-evolving",
    "I am confident",
    "I am certain",
    "strong track record",
    "proven track record",
]

# Build combined soft-warn phrases (base tells + supplemental)
def _build_soft_warns() -> list[str]:
    warns: list[str] = []
    for pattern, _ in _BASE_TELLS:
        # Skip em-dash entries — those are hard fails handled separately
        if "\u2014" in pattern or "\u2013" in pattern:
            continue
        warns.append(pattern)
    warns.extend(_SUPPLEMENTAL_TELLS)
    return warns


_SOFT_WARNS = _build_soft_warns()

# ---------------------------------------------------------------------------
# Hard-fail patterns
# ---------------------------------------------------------------------------
_EM_DASH = "\u2014"   # —
_EN_DASH = "\u2013"   # –

# Patterns that look like date ranges — en-dashes here are correct typography, not AI tells.
# e.g. "February 2025 – Present", "Jan 2020 – Dec 2022", "2020 – 2022"
import re as _re
_MONTHS = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
)
_DATE_RANGE_RE = _re.compile(
    # Month YYYY – Present/YYYY/Month  (no word boundary required before month)
    r"(?:" + _MONTHS + r")\s+\d{4}\s+\u2013\s+(?:Present|\d{4}|(?:" + _MONTHS + r"))"
    r"|\d{4}\s+\u2013\s+(?:Present|\d{4})",
    _re.IGNORECASE,
)


def _find_prose_en_dashes(text: str) -> list[str]:
    """Return snippets of spaced en-dashes that are NOT date ranges or proper-noun pairs."""
    issues = []
    for m in _re.finditer(r" \u2013 ", text):
        start = m.start()
        end = m.end()

        # Skip date ranges
        context = text[max(0, start - 40): end + 40]
        if _DATE_RANGE_RE.search(context):
            continue

        # Skip proper-noun / title-case pairs (e.g. "Atrium Health – Wake Forest",
        # "Strategy – Immunology"): word immediately before and after the dash are
        # both capitalized.
        word_before = _re.search(r"(\w+)\s*$", text[:start])
        word_after = _re.match(r"\s*(\w+)", text[end:])
        if word_before and word_after:
            wb = word_before.group(1)
            wa = word_after.group(1)
            if wb[0].isupper() and wa[0].isupper():
                continue

        snippet = text[max(0, start - 30): start + 31].replace("\n", " ")
        issues.append(f'spaced en-dash found: "...{snippet}..."')
    return issues


def _check_file(path: Path) -> list[str]:
    """Return a list of issue description strings for the given file. Empty = pass."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [f"could not read file: {exc}"]

    issues: list[str] = []

    # Hard fails
    if _EM_DASH in text:
        idx = text.index(_EM_DASH)
        snippet = text[max(0, idx - 30): idx + 31].replace("\n", " ")
        issues.append(f'em-dash found: "...{snippet}..."')

    issues.extend(_find_prose_en_dashes(text))

    # Soft warns
    text_lower = text.lower()
    for phrase in _SOFT_WARNS:
        if phrase.lower() in text_lower:
            idx = text_lower.index(phrase.lower())
            snippet = text[max(0, idx - 20): idx + len(phrase) + 20].replace("\n", " ")
            issues.append(f'"{phrase}" found: "...{snippet}..."')

    return issues


def _print_results(results: dict[str, list[str]]) -> int:
    """Print human-readable results. Returns exit code (0=all pass, 1=any fail)."""
    print("=== AI Writing Check ===")
    fail_count = 0
    for filename, issues in results.items():
        if issues:
            print(f"{filename}  FAIL")
            for issue in issues:
                print(f"  {issue}")
            fail_count += 1
        else:
            print(f"{filename}  PASS")

    print()
    if fail_count:
        print(f"{fail_count} file(s) with issues.")
        return 1
    else:
        print("All files passed.")
        return 0


def _all_txt_files() -> list[Path]:
    """Return all .tmp/*.txt files."""
    repo_root = Path(__file__).parent.parent
    tmp_dir = repo_root / ".tmp"
    if not tmp_dir.exists():
        return []
    return sorted(tmp_dir.glob("*.txt"))


def _recent_txt_files(seconds: int) -> list[Path]:
    """Return .tmp/*.txt files modified within the last N seconds."""
    repo_root = Path(__file__).parent.parent
    tmp_dir = repo_root / ".tmp"
    if not tmp_dir.exists():
        return []
    cutoff = time.time() - seconds
    return [p for p in tmp_dir.glob("*.txt") if p.stat().st_mtime >= cutoff]


def mode_check_file(filepath: str) -> int:
    path = Path(filepath)
    if not path.exists():
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        return 1
    results = {path.name: _check_file(path)}
    return _print_results(results)


def mode_all() -> int:
    files = _all_txt_files()
    if not files:
        print("No .tmp/*.txt files found.")
        return 0
    results = {p.name: _check_file(p) for p in files}
    return _print_results(results)


def mode_recent(seconds: int) -> int:
    files = _recent_txt_files(seconds)
    if not files:
        # Silent exit — nothing to check
        return 0
    results = {p.name: _check_file(p) for p in sorted(files)}
    return _print_results(results)


def mode_hook() -> int:
    """Read PostToolUse JSON from stdin; check recent files if command is relevant."""
    _TRIGGER_KEYWORDS = [
        "batch_tailor",
        "cover_letter",
        "tailor_resume",
        "generate_batch_content",
    ]

    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        payload = json.loads(raw)
        command = payload.get("tool_input", {}).get("command", "")
    except Exception:
        return 0

    if not any(kw in command for kw in _TRIGGER_KEYWORDS):
        return 0

    # Use --recent 120 logic
    mode_recent(120)
    return 0  # PostToolUse hooks always exit 0 — they inform, not block


def main() -> None:
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        sys.exit(0)

    if args[0] == "--all":
        sys.exit(mode_all())

    if args[0] == "--hook":
        sys.exit(mode_hook())

    if args[0] == "--recent":
        seconds = int(args[1]) if len(args) > 1 else 120
        sys.exit(mode_recent(seconds))

    # Treat first arg as a file path
    sys.exit(mode_check_file(args[0]))


if __name__ == "__main__":
    main()
