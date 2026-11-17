from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from task2_api.config import TODAY
from task2_api.models import Item
from task4_agent.audit import write_audit
from task4_agent.llm import generate_draft
from task4_agent.models import ReminderDraft
from task4_agent.redact import redact


def run(session: Session) -> None:
    end = TODAY + timedelta(days=30)
    items = (
        session.query(Item)
        .filter(
            Item.expiry_date.is_not(None),
            Item.expiry_date >= TODAY,
            Item.expiry_date <= end,
        )
        .order_by(Item.expiry_date, Item.id)
        .all()
    )
    for item in items:
        email = (item.responsible_email or "").strip()
        if not email:
            write_audit(
                session,
                item_id=item.id,
                item_ref=item.item_id,
                branch=item.branch,
                draft_id=None,
                action="skipped",
                status="skipped_no_email",
            )
            session.commit()
            continue
        existing = (
            session.query(ReminderDraft)
            .filter(
                ReminderDraft.item_id == item.id,
                ReminderDraft.expiry_date == item.expiry_date,
                ReminderDraft.status.in_(("pending_approval", "approved")),
            )
            .first()
        )
        if existing is not None:
            continue
        days_left = (item.expiry_date - TODAY).days
        prompt = (
            f"item_type={item.item_type}\n"
            f"item_name={item.item_name}\n"
            f"expiry_date={item.expiry_date.isoformat()}\n"
            f"days_left={days_left}"
        )
        generated = generate_draft(redact(prompt))
        draft = ReminderDraft(
            item_id=item.id,
            item_ref=item.item_id,
            branch=item.branch,
            expiry_date=item.expiry_date,
            to_email=email,
            subject=generated["subject"],
            body=generated["body"],
            status="pending_approval",
            created_at=datetime.now(timezone.utc),
        )
        session.add(draft)
        session.flush()
        write_audit(
            session,
            item_id=item.id,
            item_ref=item.item_id,
            branch=item.branch,
            draft_id=draft.id,
            action="created",
            status="pending_approval",
        )
        session.commit()
