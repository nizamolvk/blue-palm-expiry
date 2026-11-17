import csv
from datetime import date

from sqlalchemy.orm import Session

from task2_api.config import DEFAULT_CSV
from task2_api.database import Base, make_engine, make_session_factory
from task2_api.models import Item


def _blank(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _parse_date(value: str | None) -> date | None:
    text = _blank(value)
    if text is None:
        return None
    return date.fromisoformat(text)


def _parse_cost(value: str | None) -> int | None:
    text = _blank(value)
    if text is None:
        return None
    return int(text)


def load_csv(session: Session, path=DEFAULT_CSV) -> int:
    inserted = 0
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            item_id = row["item_id"].strip()
            source_text = _blank(row.get("source_row"))
            source_row = int(source_text) if source_text is not None else None
            already = (
                session.query(Item)
                .filter(Item.item_id == item_id, Item.source_row == source_row)
                .first()
            )
            if already is not None:
                continue
            session.add(
                Item(
                    item_id=item_id,
                    branch=row["branch"].strip(),
                    item_type=row["item_type"].strip(),
                    item_name=row["item_name"].strip(),
                    responsible_email=_blank(row.get("responsible_email")),
                    expiry_date=_parse_date(row.get("expiry_date")),
                    annual_cost_usd=_parse_cost(row.get("annual_cost_usd")),
                    notes=_blank(row.get("notes")),
                    source_row=source_row,
                    needs_review=_blank(row.get("needs_review")),
                    review_reason=_blank(row.get("review_reason")),
                )
            )
            inserted += 1
    session.commit()
    return inserted


def main() -> None:
    engine = make_engine()
    Base.metadata.create_all(engine)
    session = make_session_factory(engine)()
    try:
        load_csv(session)
    finally:
        session.close()


if __name__ == "__main__":
    main()
