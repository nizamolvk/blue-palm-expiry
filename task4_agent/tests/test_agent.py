from datetime import date

import pytest
from fastapi.testclient import TestClient

from task2_api.models import Item
from task4_agent.models import AuditLog, ReminderDraft
from task4_agent.redact import redact
from task4_agent.reminder_agent import run

HEADERS = {"X-API-Key": "test-key"}
MANAGER_HEADERS = {"X-API-Key": "manager-key"}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("MANAGER_API_KEY", "manager-key")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.setenv("AGENT_LOG", str(tmp_path / "agent.log"))
    from task4_agent.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        test_client.app_under_test = app
        yield test_client


def add_item(client: TestClient, **fields) -> int:
    values = {
        "item_id": "BP-1",
        "branch": "Colombo",
        "item_type": "Trade licence",
        "item_name": "Trade licence Colombo",
        "responsible_email": "nimal.p@bluepalm.example",
        "expiry_date": date(2026, 12, 15),
        "annual_cost_usd": 100,
        "notes": None,
        "source_row": 1,
        "needs_review": "no",
        "review_reason": None,
    }
    values.update(fields)
    db = client.app_under_test.state.session_factory()
    try:
        item = Item(**values)
        db.add(item)
        db.commit()
        db.refresh(item)
        return item.id
    finally:
        db.close()


def session_of(client: TestClient):
    return client.app_under_test.state.session_factory()


def test_redact_removes_passport_phone_and_email() -> None:
    cleaned = redact("Passport P7730215 phone +971501112233 email nimal.p@bluepalm.example")
    assert "P7730215" not in cleaned
    assert "+971501112233" not in cleaned
    assert "nimal.p@bluepalm.example" not in cleaned
    assert cleaned.count("[REDACTED]") == 3
    spaced = redact("call +94 77 123 4567")
    assert spaced == "call [REDACTED]"


def test_only_items_within_30_days_get_drafts(client: TestClient) -> None:
    add_item(client, item_id="BP-OLD", expiry_date=date(2026, 11, 11), source_row=1)
    add_item(client, item_id="BP-NONE", expiry_date=None, source_row=2)
    add_item(client, item_id="BP-LATER", expiry_date=date(2027, 1, 1), source_row=3)
    today_id = add_item(client, item_id="BP-TODAY", expiry_date=date(2026, 12, 1), source_row=4)
    end_id = add_item(client, item_id="BP-END", expiry_date=date(2026, 12, 31), source_row=5)
    db = session_of(client)
    try:
        run(db)
        drafts = db.query(ReminderDraft).order_by(ReminderDraft.item_id).all()
    finally:
        db.close()
    assert {row.item_id for row in drafts} == {today_id, end_id}
    assert {row.status for row in drafts} == {"pending_approval"}


def test_missing_email_is_skipped_and_logged(client: TestClient, tmp_path) -> None:
    add_item(client, item_id="BP-NOMAIL", responsible_email="", source_row=1)
    add_item(client, item_id="BP-NULLMAIL", responsible_email=None, source_row=2)
    db = session_of(client)
    try:
        run(db)
        drafts = db.query(ReminderDraft).all()
        logs = db.query(AuditLog).all()
    finally:
        db.close()
    assert drafts == []
    assert len(logs) == 2
    assert {row.action for row in logs} == {"skipped"}
    assert {row.status for row in logs} == {"skipped_no_email"}
    assert {row.item_ref for row in logs} == {"BP-NOMAIL", "BP-NULLMAIL"}
    text = (tmp_path / "agent.log").read_text(encoding="utf-8")
    assert "skipped_no_email" in text
    assert text.splitlines()[0].split()[0].endswith("Z")
    assert "nimal" not in text


def test_new_drafts_are_pending_approval(client: TestClient) -> None:
    add_item(client)
    db = session_of(client)
    try:
        run(db)
    finally:
        db.close()
    denied = client.get("/drafts")
    assert denied.status_code == 401
    response = client.get("/drafts", params={"status": "pending_approval"}, headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["status"] == "pending_approval"
    assert body[0]["item_ref"] == "BP-1"
    assert body[0]["branch"] == "Colombo"
    assert body[0]["to_email"] == "nimal.p@bluepalm.example"
    assert body[0]["created_at"].endswith("Z")
    assert body[0]["decided_by"] is None


def test_approve_works_once(client: TestClient) -> None:
    add_item(client)
    db = session_of(client)
    try:
        run(db)
        draft_id = db.query(ReminderDraft).one().id
    finally:
        db.close()
    denied = client.post(f"/drafts/{draft_id}/approve", json={"by": "Nizam"}, headers=HEADERS)
    assert denied.status_code == 401
    missing = client.post("/drafts/9999/approve", json={"by": "Nizam"}, headers=MANAGER_HEADERS)
    assert missing.status_code == 404
    first = client.post(f"/drafts/{draft_id}/approve", json={"by": "Nizam"}, headers=MANAGER_HEADERS)
    assert first.status_code == 200
    payload = first.json()
    assert payload["status"] == "approved"
    assert payload["decision"] == "approved"
    assert payload["decided_by"] == "Nizam"
    assert payload["decided_at"].endswith("Z")
    second = client.post(f"/drafts/{draft_id}/approve", json={"by": "Nizam"}, headers=MANAGER_HEADERS)
    assert second.status_code == 409


def test_name_and_status_are_validated(client: TestClient) -> None:
    add_item(client)
    db = session_of(client)
    try:
        run(db)
        draft_id = db.query(ReminderDraft).one().id
    finally:
        db.close()
    for name in ("string", "String", "  "):
        response = client.post(
            f"/drafts/{draft_id}/approve",
            json={"by": name},
            headers=MANAGER_HEADERS,
        )
        assert response.status_code == 422
    assert client.get("/drafts", params={"status": "expired"}, headers=HEADERS).status_code == 422
    assert client.get("/drafts", params={"branch": "Colmbo"}, headers=HEADERS).status_code == 422
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert set(schemas["ApproveIn"]["properties"]) == {"by"}
    assert set(schemas["RejectIn"]["properties"]) == {"by", "reject_reason"}


def test_branch_filter(client: TestClient) -> None:
    add_item(client, item_id="BP-C", branch="Colombo", source_row=1)
    add_item(client, item_id="BP-D", branch="Dubai", source_row=2)
    db = session_of(client)
    try:
        run(db)
    finally:
        db.close()
    colombo = client.get("/drafts", params={"branch": "Colombo"}, headers=HEADERS)
    assert colombo.status_code == 200
    assert [row["item_ref"] for row in colombo.json()] == ["BP-C"]
    dubai = client.get("/drafts", params={"branch": " dubai "}, headers=HEADERS)
    assert dubai.status_code == 200
    assert [row["item_ref"] for row in dubai.json()] == ["BP-D"]


def test_prompt_has_no_notes_or_pii(client: TestClient, monkeypatch) -> None:
    prompts: list[str] = []

    def spy(prompt: str) -> dict[str, str]:
        prompts.append(prompt)
        return {"subject": "Expiry reminder", "body": "template"}

    monkeypatch.setattr("task4_agent.reminder_agent.generate_draft", spy)
    add_item(
        client,
        notes="secret-note passport P7730215 call +971500000000 nimal.p@bluepalm.example",
    )
    db = session_of(client)
    try:
        run(db)
        draft = db.query(ReminderDraft).one()
    finally:
        db.close()
    assert len(prompts) == 1
    prompt = prompts[0]
    assert "secret-note" not in prompt
    assert "P7730215" not in prompt
    assert "+971500000000" not in prompt
    assert "nimal.p@bluepalm.example" not in prompt
    assert "notes" not in prompt
    assert draft.to_email == "nimal.p@bluepalm.example"
    assert draft.body == "template"


def test_running_twice_creates_no_duplicates(client: TestClient) -> None:
    add_item(client)
    db = session_of(client)
    try:
        run(db)
        run(db)
        drafts = db.query(ReminderDraft).all()
        assert len(drafts) == 1
        draft_id = drafts[0].id
    finally:
        db.close()
    approved = client.post(
        f"/drafts/{draft_id}/approve",
        json={"by": "Nizam"},
        headers=MANAGER_HEADERS,
    )
    assert approved.status_code == 200
    db = session_of(client)
    try:
        run(db)
        drafts = db.query(ReminderDraft).all()
    finally:
        db.close()
    assert len(drafts) == 1
    assert drafts[0].status == "approved"


def test_rejected_draft_blocks_another_draft(client: TestClient) -> None:
    add_item(client)
    db = session_of(client)
    try:
        run(db)
        draft_id = db.query(ReminderDraft).one().id
    finally:
        db.close()
    rejected = client.post(
        f"/drafts/{draft_id}/reject",
        json={"by": "Nizam", "reject_reason": "not now"},
        headers=MANAGER_HEADERS,
    )
    assert rejected.status_code == 200
    db = session_of(client)
    try:
        run(db)
        drafts = db.query(ReminderDraft).all()
    finally:
        db.close()
    assert len(drafts) == 1
    assert drafts[0].id == draft_id
    assert drafts[0].status == "rejected"


def test_database_blocks_second_draft_for_same_expiry(client: TestClient) -> None:
    from sqlalchemy.exc import IntegrityError

    add_item(client)
    db = session_of(client)
    try:
        run(db)
        original = db.query(ReminderDraft).one()
        db.add(
            ReminderDraft(
                item_id=original.item_id,
                item_ref=original.item_ref,
                branch=original.branch,
                expiry_date=original.expiry_date,
                to_email=original.to_email,
                subject="second",
                body="second",
                status="rejected",
                created_at=original.created_at,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_generated_text_redacts_passport_and_spaced_phone(client: TestClient) -> None:
    add_item(client, item_name="Permit P7730215 call +94 77 123 4567")
    db = session_of(client)
    try:
        run(db)
        draft = db.query(ReminderDraft).one()
    finally:
        db.close()
    assert "P7730215" not in draft.subject
    assert "P7730215" not in draft.body
    assert "+94" not in draft.body
    assert "123 4567" not in draft.body
    assert "[REDACTED]" in draft.body


def test_reject_is_manager_only_and_decisions_are_logged(client: TestClient, tmp_path) -> None:
    approve_item = add_item(client, item_id="BP-A", source_row=1)
    reject_item = add_item(client, item_id="BP-R", source_row=2)
    db = session_of(client)
    try:
        run(db)
        drafts = {row.item_id: row.id for row in db.query(ReminderDraft).all()}
    finally:
        db.close()
    approve_id = drafts[approve_item]
    reject_id = drafts[reject_item]

    denied = client.post(
        f"/drafts/{reject_id}/reject",
        json={"by": "Nizam"},
        headers=HEADERS,
    )
    assert denied.status_code == 401

    approved = client.post(
        f"/drafts/{approve_id}/approve",
        json={"by": "Nizam"},
        headers=MANAGER_HEADERS,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    rejected = client.post(
        f"/drafts/{reject_id}/reject",
        json={"by": "Nizam", "reject_reason": "not now"},
        headers=MANAGER_HEADERS,
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    db = session_of(client)
    try:
        logs = db.query(AuditLog).all()
        approved_draft = db.query(ReminderDraft).filter(ReminderDraft.id == approve_id).one()
    finally:
        db.close()
    assert approved_draft.status == "approved"
    actions = {row.action for row in logs}
    assert actions == {"created", "approved", "rejected"}
    assert "sent" not in actions
    for row in logs:
        assert row.timestamp is not None
        assert row.draft_id is not None
        assert row.status in {"pending_approval", "approved", "rejected"}
        assert row.item_id in {approve_item, reject_item}
    assert {row.item_id for row in logs if row.action == "created"} == {approve_item, reject_item}
    assert {row.actor for row in logs if row.action == "created"} == {None}
    approved_log = next(row for row in logs if row.action == "approved")
    rejected_log = next(row for row in logs if row.action == "rejected")
    assert approved_log.item_id == approve_item
    assert approved_log.draft_id == approve_id
    assert approved_log.status == "approved"
    assert approved_log.actor == "Nizam"
    assert rejected_log.item_id == reject_item
    assert rejected_log.draft_id == reject_id
    assert rejected_log.status == "rejected"
    assert rejected_log.actor == "Nizam"

    denied_history = client.get("/activity")
    assert denied_history.status_code == 401
    history = client.get("/activity", headers=HEADERS)
    assert history.status_code == 200
    payload = history.json()
    assert {row["action"] for row in payload} == {"created", "approved", "rejected"}
    approved_body = next(row for row in payload if row["action"] == "approved")
    rejected_body = next(row for row in payload if row["action"] == "rejected")
    assert approved_body["actor"] == "Nizam"
    assert approved_body["draft_id"] == approve_id
    assert approved_body["item_id"] == approve_item
    assert approved_body["status"] == "approved"
    assert approved_body["timestamp"].endswith("Z")
    assert rejected_body["actor"] == "Nizam"
    assert rejected_body["draft_id"] == reject_id
    assert "nimal.p@bluepalm.example" not in history.text
    text = (tmp_path / "agent.log").read_text(encoding="utf-8")
    assert "actor=Nizam" in text
    assert "nimal.p@bluepalm.example" not in text


def test_production_rejects_placeholder_key(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("MANAGER_API_KEY", "manager-key")
    monkeypatch.setenv("APP_ENV", "development")
    from task4_agent.main import create_app

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("API_KEY", "dev-api-key-change-me")
    with pytest.raises(RuntimeError):
        create_app()
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("MANAGER_API_KEY", "dev-api-key-change-me")
    with pytest.raises(RuntimeError):
        create_app()
