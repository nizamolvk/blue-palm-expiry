from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Mapped, mapped_column

from task2_api.database import Base
from task2_api.models import Item  # noqa: F401


class ReminderDraft(Base):
    __tablename__ = "reminder_drafts"
    __table_args__ = (
        UniqueConstraint("item_id", "expiry_date", name="uq_reminder_draft_item_expiry"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False, index=True)
    item_ref: Mapped[str] = mapped_column(String, nullable=False)
    branch: Mapped[str] = mapped_column(String, nullable=False, index=True)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_email: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    decision: Mapped[str | None] = mapped_column(String, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_by: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    item_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    branch: Mapped[str | None] = mapped_column(String, nullable=True)
    draft_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    actor: Mapped[str | None] = mapped_column(String, nullable=True)


def ensure_task4_schema(bind: Engine | Connection) -> None:
    engine = bind.engine if isinstance(bind, Connection) else bind
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "audit_log" in tables:
        columns = {column["name"] for column in inspector.get_columns("audit_log")}
        if "actor" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE audit_log ADD COLUMN actor VARCHAR"))
    if "reminder_drafts" in tables:
        names = {index["name"] for index in inspector.get_indexes("reminder_drafts")}
        names.update(item["name"] for item in inspector.get_unique_constraints("reminder_drafts"))
        if "uq_reminder_draft_item_expiry" not in names:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uq_reminder_draft_item_expiry "
                        "ON reminder_drafts (item_id, expiry_date)"
                    )
                )
