import argparse
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from task2_api.database import make_engine, make_session_factory
from task4_agent.audit import write_audit
from task4_agent.models import ReminderDraft, ensure_task4_schema


class DraftNotFound(Exception):
    pass


class NotPending(Exception):
    pass


def _pending(session: Session, draft_id: int) -> ReminderDraft:
    draft = session.get(ReminderDraft, draft_id)
    if draft is None:
        raise DraftNotFound()
    if draft.status != "pending_approval":
        raise NotPending()
    return draft


def _decide(session: Session, draft: ReminderDraft, action: str, status: str, by: str) -> ReminderDraft:
    write_audit(
        session,
        item_id=draft.item_id,
        item_ref=draft.item_ref,
        branch=draft.branch,
        draft_id=draft.id,
        action=action,
        status=status,
        actor=by,
    )
    session.commit()
    session.refresh(draft)
    return draft


def approve_draft(session: Session, draft_id: int, by: str) -> ReminderDraft:
    # Nothing is sent automatically.
    draft = _pending(session, draft_id)
    draft.status = "approved"
    draft.decision = "approved"
    draft.decided_by = by
    draft.decided_at = datetime.now(timezone.utc)
    draft.reject_reason = None
    return _decide(session, draft, "approved", "approved", by)


def reject_draft(
    session: Session,
    draft_id: int,
    by: str,
    reject_reason: str | None = None,
) -> ReminderDraft:
    draft = _pending(session, draft_id)
    draft.status = "rejected"
    draft.decision = "rejected"
    draft.decided_by = by
    draft.decided_at = datetime.now(timezone.utc)
    draft.reject_reason = reject_reason
    return _decide(session, draft, "rejected", "rejected", by)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=int, required=True)
    parser.add_argument("--by", required=True)
    args = parser.parse_args(argv)
    engine = make_engine()
    ensure_task4_schema(engine)
    session = make_session_factory(engine)()
    try:
        approve_draft(session, args.id, args.by)
    except (DraftNotFound, NotPending):
        raise SystemExit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
