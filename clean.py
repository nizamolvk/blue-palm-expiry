"""Clean the Blue Palm expiry spreadsheet.

Safe fixes are applied in place. Dates are written as YYYY-MM-DD, or left
blank when the text is missing, not a date, or could be read two ways.
Invalid email addresses are cleared. Anything still uncertain is marked for
a person to review. The review date is 1 December 2026: an expiry before
that day is a real expiry, not a data error.
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

REVIEW_DATE = date(2026, 12, 1)
REVIEW_DATE_TEXT = "1 December 2026"

ORIGINAL_COLUMNS = [
    "item_id",
    "branch",
    "item_type",
    "item_name",
    "responsible_email",
    "expiry_date",
    "annual_cost_usd",
    "notes",
]
OUTPUT_COLUMNS = ORIGINAL_COLUMNS + ["source_row", "needs_review", "review_reason"]

CANONICAL_BRANCHES = {"colombo": "Colombo", "dubai": "Dubai"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
NAMED_DATE_RE = re.compile(r"^(\d{1,2}) ([A-Za-z]{3}) (\d{4})$")
SLASH_DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
PASSPORT_RE = re.compile(r"(?i)\bpassport(?:\s+no\.?)?\s+[A-Z0-9]+\b")
PHONE_RE = re.compile(r"\+\d{1,3}(?:\s\d+){1,4}")
CITY_RE = re.compile(r"\b(Colombo|Dubai)\b")

ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT / "data" / "blue_palm_expiry_items.csv"


def clean_spreadsheet(source: Path, output_dir: Path) -> None:
    rows = _read_rows(source)
    kept, removed = _drop_exact_duplicates(rows)
    email_branch = _email_branch_hints(kept)
    cleaned, fixes, reviews = _clean_rows(kept, email_branch)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "clean_items.csv", cleaned)
    report = _render_report(
        source_name=source.name,
        source_count=len(rows),
        clean_count=len(cleaned),
        fixes=fixes,
        reviews=reviews,
        removed=removed,
    )
    (output_dir / "data_issues.md").write_text(report, encoding="utf-8")


def _read_rows(source: Path) -> list[dict[str, str]]:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [name for name in ORIGINAL_COLUMNS if name not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Missing columns: {', '.join(missing)}")
        rows = []
        for offset, raw in enumerate(reader, start=2):
            row = {name: (raw.get(name) or "") for name in ORIGINAL_COLUMNS}
            row["source_row"] = str(offset)
            rows.append(row)
    return rows


def _row_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row[name] for name in ORIGINAL_COLUMNS)


def _drop_exact_duplicates(
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[tuple[dict[str, str], dict[str, str]]]]:
    seen: dict[tuple[str, ...], dict[str, str]] = {}
    kept: list[dict[str, str]] = []
    removed: list[tuple[dict[str, str], dict[str, str]]] = []
    for row in rows:
        key = _row_key(row)
        if key in seen:
            removed.append((seen[key], row))
            continue
        seen[key] = row
        kept.append(row)
    return kept, removed


def _email_branch_hints(rows: list[dict[str, str]]) -> dict[str, str]:
    """Map an email to a branch only when every consistent row agrees."""
    found: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        branch = _resolve_branch(row["branch"])
        if branch is None:
            continue
        cities = _cities(row["item_name"])
        if cities and cities != {branch}:
            continue
        email = row["responsible_email"].strip().lower()
        if email:
            found[email].add(branch)
    return {email: next(iter(branches)) for email, branches in found.items() if len(branches) == 1}


def _levenshtein(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            current.append(
                min(
                    current[j - 1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def _resolve_branch(value: str) -> str | None:
    """Return Colombo or Dubai, including a close spelling such as Colmbo."""
    token = value.strip().casefold()
    if not token:
        return None
    exact = CANONICAL_BRANCHES.get(token)
    if exact:
        return exact
    scored = sorted(
        (_levenshtein(token, key), label) for key, label in CANONICAL_BRANCHES.items()
    )
    best_distance, best_label = scored[0]
    next_distance = scored[1][0]
    if best_distance <= 2 and best_distance < next_distance:
        return best_label
    return None


def _cities(item_name: str) -> set[str]:
    return set(CITY_RE.findall(item_name))


def _clean_rows(
    rows: list[dict[str, str]],
    email_branch: dict[str, str],
) -> tuple[list[dict[str, str]], list[str], list[str]]:
    repeated_ids = {row["item_id"] for row in rows if sum(r["item_id"] == row["item_id"] for r in rows) > 1}
    conflicting = [row for row in rows if row["item_id"] in repeated_ids]

    cleaned: list[dict[str, str]] = []
    fixes: list[str] = []
    reviews: list[str] = []

    if conflicting:
        by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in conflicting:
            by_id[row["item_id"]].append(row)
        for item_id, group in by_id.items():
            reviews.append(
                f"`{item_id}` was not merged. " + "; ".join(_conflict_part(row) for row in group) + "."
            )

    for row in rows:
        reasons: list[str] = []
        item_id = row["item_id"]
        line = row["source_row"]

        expiry, date_fix, date_review = _clean_date(row["expiry_date"])
        if date_fix:
            fixes.append(f"`{item_id}` line {line}: {date_fix}")
        if date_review:
            reasons.append(date_review)

        branch, branch_fix, branch_review = _clean_branch(row, email_branch)
        if branch_fix:
            fixes.append(f"`{item_id}` line {line}: {branch_fix}")
        if branch_review:
            reasons.append(branch_review)

        email, email_review = _clean_email(row["responsible_email"])
        if email_review:
            reasons.append(email_review)

        cost, cost_review = _clean_cost(row["annual_cost_usd"])
        if cost_review:
            reasons.append(cost_review)

        notes, note_fix = _redact_notes(row["notes"])
        if note_fix:
            fixes.append(f"`{item_id}` line {line}: {note_fix}")

        if item_id in repeated_ids:
            reasons.append("same item id appears with different values, and both rows were kept")

        for reason in reasons:
            reviews.append(f"`{item_id}` line {line}: {reason}")

        cleaned.append(
            {
                "item_id": item_id,
                "branch": branch,
                "item_type": row["item_type"],
                "item_name": row["item_name"],
                "responsible_email": email,
                "expiry_date": expiry,
                "annual_cost_usd": cost,
                "notes": notes,
                "source_row": line,
                "needs_review": "yes" if reasons else "no",
                "review_reason": "; ".join(reasons),
            }
        )
    return cleaned, fixes, reviews


def _clean_date(raw: str) -> tuple[str, str | None, str | None]:
    text = raw.strip()
    if not text:
        return "", None, "expiry date is blank"

    iso = ISO_DATE_RE.fullmatch(text)
    if iso:
        parsed = _valid_date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        if parsed:
            return parsed.isoformat(), None, None
        return "", None, f"expiry date `{raw}` is not a real calendar date, so it was cleared"

    named = NAMED_DATE_RE.fullmatch(text)
    if named:
        parsed = _parse_named(named.group(1), named.group(2), named.group(3))
        if parsed:
            return parsed.isoformat(), f"`{raw}` → `{parsed.isoformat()}`", None
        return "", None, f"expiry date `{raw}` is not a real calendar date, so it was cleared"

    slash = SLASH_DATE_RE.fullmatch(text)
    if slash:
        first, second, year = int(slash.group(1)), int(slash.group(2)), int(slash.group(3))
        if first <= 12 and second <= 12:
            return (
                "",
                None,
                f"`{raw}` could be day/month/year or month/day/year, so it was cleared",
            )
        if first > 12 and second <= 12:
            parsed = _valid_date(year, second, first)
            if parsed:
                return (
                    parsed.isoformat(),
                    f"`{raw}` → `{parsed.isoformat()}` ({first} cannot be a month)",
                    None,
                )
        if second > 12 and first <= 12:
            parsed = _valid_date(year, first, second)
            if parsed:
                return parsed.isoformat(), f"`{raw}` → `{parsed.isoformat()}`", None
        return "", None, f"expiry date `{raw}` is not a real calendar date, so it was cleared"

    return "", None, f"expiry date `{raw}` is not a date, so it was cleared"


def _conflict_part(row: dict[str, str]) -> str:
    expiry = row["expiry_date"] or "blank"
    text = f"Line {row['source_row']} expires `{expiry}`"
    note = row["notes"].strip()
    if note and not PASSPORT_RE.search(note) and not PHONE_RE.search(note):
        text += f" (note: {note})"
    return text


def _parse_named(day: str, month: str, year: str) -> date | None:
    try:
        parsed = datetime.strptime(f"{int(day)} {month.title()} {year}", "%d %b %Y")
    except ValueError:
        return None
    return parsed.date()


def _valid_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _clean_branch(
    row: dict[str, str],
    email_branch: dict[str, str],
) -> tuple[str, str | None, str | None]:
    raw = row["branch"]
    canonical = _resolve_branch(raw)
    cities = _cities(row["item_name"])
    expected = email_branch.get(row["responsible_email"].strip().lower())
    name_clash = bool(cities) and (canonical is None or cities != {canonical})
    email_clash = expected is not None and canonical != expected

    if canonical is None:
        detail = f"branch `{raw}` was left as written"
        hints = _conflict_hints(cities, expected)
        if hints:
            detail += f". {hints[0].upper()}{hints[1:]}. The branch was not changed"
        return raw, None, detail

    fix = None
    if raw != canonical:
        fix = f"branch `{raw}` → `{canonical}`"

    if name_clash or email_clash:
        detail = _conflict_hints(cities, expected)
        if fix:
            detail = (
                f"branch was standardised to `{canonical}`, but {detail[:1].lower()}{detail[1:]}. "
                "The branch was not switched"
            )
        else:
            detail = f"{detail}. The branch was not switched"
        return canonical, fix, detail

    return canonical, fix, None


def _conflict_hints(cities: set[str], expected: str | None) -> str:
    parts = []
    if cities:
        listed = " and ".join(sorted(cities))
        parts.append(f"the item name says {listed}")
    if expected:
        parts.append(
            f"this email belongs to {expected} on the other consistent rows"
        )
    return ", and ".join(parts)


def _clean_email(raw: str) -> tuple[str, str | None]:
    text = raw.strip()
    if EMAIL_RE.fullmatch(text):
        return text, None
    if " " in text and "@" not in text:
        local, domain = text.split(None, 1)
        likely = f"{local}@{domain}"
        return (
            "",
            f"email `{text}` has a space where `@` would be. "
            f"A likely address is `{likely}`. The clean file leaves the email empty",
        )
    if "@" in text and "." not in text.split("@", 1)[1]:
        return (
            "",
            f"email `{text}` has no domain suffix. `.example` was not added, and the email was cleared",
        )
    return "", f"email `{text}` is not a valid address, so it was cleared"


def _clean_cost(raw: str) -> tuple[str, str | None]:
    text = raw.strip()
    if re.fullmatch(r"-?\d+", text):
        value = int(text)
        written = str(value)
        if value < 0:
            return written, f"annual cost is `{written}`"
        if value == 0:
            return written, f"annual cost is `0` (free versus missing is unclear)"
        return written, None
    return raw, f"annual cost `{raw}` is not a plain integer and was left unchanged"


def _redact_notes(raw: str) -> tuple[str, str | None]:
    found_passport = PASSPORT_RE.search(raw) is not None
    found_phone = PHONE_RE.search(raw) is not None
    if not found_passport and not found_phone:
        return raw, None
    redacted = PHONE_RE.sub("[REDACTED]", raw)
    redacted = PASSPORT_RE.sub("[REDACTED]", redacted)
    parts = []
    if found_passport:
        parts.append("passport number")
    if found_phone:
        parts.append("phone number")
    joined = " and ".join(parts)
    return redacted, f"{joined} in notes replaced with `[REDACTED]` (value not repeated)"


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _render_report(
    source_name: str,
    source_count: int,
    clean_count: int,
    fixes: list[str],
    reviews: list[str],
    removed: list[tuple[dict[str, str], dict[str, str]]],
) -> str:
    duplicate_lines = []
    for kept, dropped in removed:
        duplicate_lines.append(
            f"`{kept['item_id']}`: kept line {kept['source_row']}, "
            f"removed line {dropped['source_row']}"
        )

    date_fixes = [line for line in fixes if "→" in line and "branch" not in line]
    branch_fixes = [line for line in fixes if line.split(": ", 1)[-1].startswith("branch ")]
    note_fixes = [line for line in fixes if "replaced with" in line]

    id_reviews = [line for line in reviews if "was not merged" in line]
    row_reviews = [line for line in reviews if "was not merged" not in line]
    date_reviews = [line for line in row_reviews if "expiry date" in line or "could be day/month" in line]
    branch_reviews = [line for line in row_reviews if "branch" in line]
    email_reviews = [line for line in row_reviews if "email `" in line]
    cost_reviews = [line for line in row_reviews if "annual cost" in line]
    other_reviews = [
        line
        for line in row_reviews
        if line not in date_reviews + branch_reviews + email_reviews + cost_reviews
        and "same item id" not in line
    ]

    def bullets(lines: list[str]) -> str:
        if not lines:
            return "- None\n"
        rendered = []
        for line in lines:
            if not line.endswith("."):
                line += "."
            rendered.append(f"- {line}\n")
        return "".join(rendered)

    removed_count = source_count - clean_count
    body = f"""# Data issues

Reviewed against {REVIEW_DATE_TEXT} ({REVIEW_DATE.isoformat()}). An expiry before that date is a real expiry, not a data error.

Source file: `data/{source_name}` ({source_count} data rows).
Clean file: `clean_items.csv` ({clean_count} data rows). {removed_count} later exact-duplicate copies were removed.

`needs_review` is `yes` when a row still has a problem a person must decide. `review_reason` lists those problems, separated by semicolons. Safe fixes on those rows are already applied where noted below.

## Fixed

### Exact duplicates removed

The later identical copy was removed. The earlier row was kept.

{bullets(duplicate_lines)}
### Dates standardised

Written as `YYYY-MM-DD`. Only values with one valid calendar reading were changed.

{bullets(date_fixes)}
### Branch spelling

{bullets(branch_fixes)}
Rows whose item name or email points at the other city are still listed under needs human review. The branch was not switched.

### Personal information redacted

Passport numbers and phone numbers in notes were replaced with `[REDACTED]`. The values are not repeated here.

{bullets(note_fixes)}
## Needs human review

### Same id, different values

{bullets(id_reviews)}
### Dates cleared or still blank

{bullets(date_reviews)}
### Branch left unresolved

{bullets(branch_reviews)}
### Emails cleared

{bullets(email_reviews)}
### Costs left as written

{bullets(cost_reviews)}
"""
    if other_reviews:
        body += "### Other\n\n" + bullets(other_reviews) + "\n"

    body += """## Not treated as data errors

- `licence` in `Trade licence` is consistent British spelling.
- The number in `item_name` matches `item_id` (`BP-1000` is `#1`).
- Expiry dates before 1 December 2026 were left as real expiries.
"""
    return body


def main() -> None:
    clean_spreadsheet(DEFAULT_SOURCE, ROOT)


if __name__ == "__main__":
    main()
