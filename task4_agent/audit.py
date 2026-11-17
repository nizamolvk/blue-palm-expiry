import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from task2_api.config import ROOT
from task4_agent.models import AuditLog


def log_path() -> Path:
    configured = os.environ.get("AGENT_LOG")
    if configured:
        return Path(configured)
    return ROOT / "logs" / "agent.log"


def format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def write_audit(
    session: Session,
    *,
    item_id: int | None,
    item_ref: str | None,
    branch: str | None,
    draft_id: int | None,
    action: str,
    status: str,
    actor: str | None = None,
) -> None:
    timestamp = datetime.now(timezone.utc)
    session.add(
        AuditLog(
            timestamp=timestamp,
            item_id=item_id,
            item_ref=item_ref,
            branch=branch,
            draft_id=draft_id,
            action=action,
            status=status,
            actor=actor,
        )
    )
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    item_text = "-" if item_id is None else str(item_id)
    ref_text = "-" if item_ref is None else item_ref
    branch_text = "-" if branch is None else branch
    draft_text = "-" if draft_id is None else str(draft_id)
    actor_text = "-" if not actor else actor
    line = (
        f"{format_utc(timestamp)} item_id={item_text} item_ref={ref_text} "
        f"branch={branch_text} draft_id={draft_text} action={action} status={status} "
        f"actor={actor_text}\n"
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
