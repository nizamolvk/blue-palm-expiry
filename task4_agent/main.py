import os
from datetime import datetime

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, field_serializer, field_validator
from sqlalchemy.orm import Session

from task2_api.auth import require_api_key
from task2_api.database import make_engine, make_session_factory
from task4_agent.approve import DraftNotFound, NotPending, approve_draft, reject_draft
from task4_agent.audit import format_utc
from task4_agent.models import AuditLog, ReminderDraft, ensure_task4_schema

PLACEHOLDER_KEY = "dev-api-key-change-me"
DRAFT_STATUSES = {"pending_approval", "approved", "rejected"}
BRANCHES = {"colombo": "Colombo", "dubai": "Dubai"}


class ApproveIn(BaseModel):
    by: str

    @field_validator("by")
    @classmethod
    def check_by(cls, value: str) -> str:
        name = value.strip()
        if not name or name.casefold() == "string":
            raise ValueError("by must be a non-empty name")
        return name


class RejectIn(ApproveIn):
    reject_reason: str | None = None

    @field_validator("reject_reason")
    @classmethod
    def blank_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None


class DraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    item_ref: str
    branch: str
    to_email: str
    subject: str
    body: str
    status: str
    decision: str | None
    reject_reason: str | None
    created_at: datetime
    decided_by: str | None
    decided_at: datetime | None

    @field_serializer("created_at", "decided_at")
    def serialize_time(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return format_utc(value)


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    item_id: int | None
    item_ref: str | None
    branch: str | None
    draft_id: int | None
    action: str
    status: str
    actor: str | None

    @field_serializer("timestamp")
    def serialize_time(self, value: datetime) -> str:
        return format_utc(value)


def require_manager_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("MANAGER_API_KEY")
    if not expected or x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")


def normalise_branch(branch: str | None) -> str | None:
    if branch is None:
        return None
    canonical = BRANCHES.get(branch.strip().casefold())
    if canonical is None:
        raise HTTPException(status_code=422, detail="branch must be Colombo or Dubai")
    return canonical


def normalise_status(status: str | None) -> str | None:
    if status is None:
        return None
    if status not in DRAFT_STATUSES:
        raise HTTPException(status_code=422, detail="invalid status")
    return status


def _guard_production_keys() -> None:
    if os.environ.get("APP_ENV") != "production":
        return
    for name in ("API_KEY", "MANAGER_API_KEY"):
        if os.environ.get(name) == PLACEHOLDER_KEY:
            raise RuntimeError(f"{name} must not use the placeholder in production")


def create_app(engine=None) -> FastAPI:
    _guard_production_keys()
    engine = make_engine() if engine is None else engine
    ensure_task4_schema(engine)
    session_factory = make_session_factory(engine)
    app = FastAPI()
    app.state.session_factory = session_factory

    def get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    reader = APIRouter(dependencies=[Depends(require_api_key)])
    manager = APIRouter(dependencies=[Depends(require_manager_api_key)])

    @reader.get("/drafts", response_model=list[DraftOut])
    def list_drafts(
        status: str | None = None,
        branch: str | None = None,
        db: Session = Depends(get_db),
    ):
        status = normalise_status(status)
        branch = normalise_branch(branch)
        query = db.query(ReminderDraft)
        if status:
            query = query.filter(ReminderDraft.status == status)
        if branch:
            query = query.filter(ReminderDraft.branch == branch)
        return query.order_by(ReminderDraft.id).all()

    @reader.get("/activity", response_model=list[ActivityOut])
    def list_activity(db: Session = Depends(get_db)):
        return db.query(AuditLog).order_by(AuditLog.id).all()

    @manager.post("/drafts/{draft_id}/approve", response_model=DraftOut)
    def approve(draft_id: int, body: ApproveIn, db: Session = Depends(get_db)):
        try:
            return approve_draft(db, draft_id, body.by)
        except DraftNotFound:
            raise HTTPException(status_code=404, detail="draft not found")
        except NotPending:
            raise HTTPException(status_code=409, detail="draft is not pending approval")

    @manager.post("/drafts/{draft_id}/reject", response_model=DraftOut)
    def reject(draft_id: int, body: RejectIn, db: Session = Depends(get_db)):
        try:
            return reject_draft(db, draft_id, body.by, body.reject_reason)
        except DraftNotFound:
            raise HTTPException(status_code=404, detail="draft not found")
        except NotPending:
            raise HTTPException(status_code=409, detail="draft is not pending approval")

    app.include_router(reader)
    app.include_router(manager)
    return app


app = create_app()
