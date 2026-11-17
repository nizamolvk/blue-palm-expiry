import csv
import re
from datetime import date
from pathlib import Path

import clean

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "blue_palm_expiry_items.csv"
SECRET_RE = re.compile(r"\b[A-Z]\d{5,}\b|\+\d[\d ]+\d")


def _run(tmp_path: Path) -> tuple[list[dict[str, str]], str]:
    clean.clean_spreadsheet(SOURCE, tmp_path)
    with (tmp_path / "clean_items.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    report = (tmp_path / "data_issues.md").read_text(encoding="utf-8")
    return rows, report


def _only(rows: list[dict[str, str]], item_id: str) -> dict[str, str]:
    matches = [row for row in rows if row["item_id"] == item_id]
    assert len(matches) == 1
    return matches[0]


def test_exact_duplicates_removed(tmp_path: Path) -> None:
    rows, _report = _run(tmp_path)
    ids = [row["item_id"] for row in rows]

    with SOURCE.open(newline="", encoding="utf-8") as handle:
        source_count = sum(1 for _ in csv.DictReader(handle))
    assert source_count == 56
    assert len(rows) == source_count - 3
    assert ids.count("BP-1017") == 1
    assert ids.count("BP-1026") == 1
    assert ids.count("BP-1004") == 1
    assert ids.count("BP-1020") == 2

    kept = [row for row in rows if row["item_id"] == "BP-1020"]
    assert {row["expiry_date"] for row in kept} == {"2027-11-13", "2026-11-13"}
    assert all(row["needs_review"] == "yes" for row in kept)


def test_unambiguous_dates_normalised(tmp_path: Path) -> None:
    rows, _report = _run(tmp_path)

    assert _only(rows, "BP-1022")["expiry_date"] == "2026-12-06"
    assert _only(rows, "BP-1008")["expiry_date"] == "2027-01-01"
    assert _only(rows, "BP-1015")["expiry_date"] == "2027-04-30"


def test_unclear_values_are_flagged_not_guessed(tmp_path: Path) -> None:
    rows, report = _run(tmp_path)

    ambiguous = _only(rows, "BP-1003")
    assert ambiguous["expiry_date"] == ""
    assert ambiguous["needs_review"] == "yes"
    assert "08/12/2026" in ambiguous["review_reason"]
    assert "08/12/2026" in report

    assert _only(rows, "BP-1027")["expiry_date"] == ""
    assert "TBC" in _only(rows, "BP-1027")["review_reason"]
    assert _only(rows, "BP-1027")["needs_review"] == "yes"
    assert _only(rows, "BP-1010")["expiry_date"] == ""
    assert _only(rows, "BP-1010")["needs_review"] == "yes"

    shanika = _only(rows, "BP-1014")
    assert shanika["responsible_email"] == ""
    assert shanika["needs_review"] == "yes"
    assert "shanika.r@bluepalm" in shanika["review_reason"]

    colmbo = _only(rows, "BP-1019")
    assert colmbo["branch"] == "Colombo"
    assert colmbo["needs_review"] == "yes"
    assert "Dubai" in colmbo["review_reason"]

    negative = _only(rows, "BP-1012")
    assert negative["annual_cost_usd"] == "-450"
    assert negative["needs_review"] == "yes"

    with SOURCE.open(newline="", encoding="utf-8") as handle:
        source_rows = list(csv.DictReader(handle))
    secrets = {
        match
        for row in source_rows
        for match in SECRET_RE.findall(row["notes"])
    }
    assert secrets
    clean_notes = "\n".join(row["notes"] for row in rows)
    for secret in secrets:
        assert secret not in clean_notes
        assert secret not in report


def test_expiry_dates_are_iso_or_empty(tmp_path: Path) -> None:
    rows, _report = _run(tmp_path)

    for row in rows:
        value = row["expiry_date"]
        if value == "":
            continue
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
        date.fromisoformat(value)

    assert _only(rows, "BP-1027")["expiry_date"] == ""
    assert _only(rows, "BP-1003")["expiry_date"] == ""
