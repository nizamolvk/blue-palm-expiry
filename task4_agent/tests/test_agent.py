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
