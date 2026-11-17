from datetime import date

import pytest
from fastapi.testclient import TestClient

HEADERS = {"X-API-Key": "test-key"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("API_KEY", "test-key")
    from task2_api.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        test_client.app_under_test = app
        yield test_client


def add_item(client: TestClient, **fields) -> None:
    from task2_api.models import Item

    values = {
        "item_id": "BP-1",
        "branch": "Colombo",
        "item_type": "Trade licence",
        "item_name": "Trade licence Colombo",
        "responsible_email": "nimal.p@bluepalm.example",
        "expiry_date": date(2026, 12, 15),
        "annual_cost_usd": 100,
        "notes": "passport P7730215",
        "source_row": 1,
        "needs_review": "no",
        "review_reason": None,
    }
    values.update(fields)
    db = client.app_under_test.state.session_factory()
    try:
        db.add(Item(**values))
        db.commit()
    finally:
        db.close()


def test_missing_api_key_is_rejected(client: TestClient) -> None:
    response = client.get("/items")
    assert response.status_code == 401


def test_branch_filter(client: TestClient) -> None:
    add_item(client, item_id="BP-C", branch="Colombo", source_row=1)
    add_item(client, item_id="BP-D", branch="Dubai", source_row=2)
    response = client.get("/items", params={"branch": "Colombo"}, headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert [row["item_id"] for row in body] == ["BP-C"]
    assert body[0]["branch"] == "Colombo"


def test_branch_filter_ignores_case_and_spaces(client: TestClient) -> None:
    add_item(client, item_id="BP-D", branch="Dubai", expiry_date=date(2026, 12, 10), source_row=2)
    add_item(client, item_id="BP-C", branch="Colombo", source_row=1)
    for value in ("dubai", "DUBAI", " Dubai "):
        response = client.get("/items", params={"branch": value}, headers=HEADERS)
        assert response.status_code == 200
        assert [row["item_id"] for row in response.json()] == ["BP-D"]
    expiring = client.get("/items/expiring", params={"branch": " dubai "}, headers=HEADERS)
    assert expiring.status_code == 200
    assert [row["item_id"] for row in expiring.json()] == ["BP-D"]
    assert client.get("/items", params={"branch": "Colmbo"}, headers=HEADERS).status_code == 422
    assert client.get("/items/expiring", params={"branch": "Colmbo"}, headers=HEADERS).status_code == 422


def test_expired_items_are_marked(client: TestClient) -> None:
    add_item(client, item_id="BP-OLD", expiry_date=date(2026, 11, 11), source_row=3)
    add_item(client, item_id="BP-LATER", expiry_date=date(2027, 6, 1), source_row=4)
    response = client.get("/items/expiring", params={"days": 30}, headers=HEADERS)
    assert response.status_code == 200
    body = {row["item_id"]: row for row in response.json()}
    assert body["BP-OLD"]["status"] == "expired"
    assert body["BP-OLD"]["days_left"] < 0
    assert "BP-LATER" not in body


def test_post_rejects_bad_branch_and_email(client: TestClient) -> None:
    payload = {
        "item_id": "BP-NEW",
        "branch": "Colombo",
        "item_type": "Office lease",
        "item_name": "Office lease Colombo",
        "responsible_email": "nimal.p@bluepalm.example",
        "expiry_date": "2027-03-01",
        "annual_cost_usd": 12000,
    }
    bad_branch = dict(payload, branch="Colmbo")
    bad_email = dict(payload, responsible_email="shanika.r@bluepalm")
    assert client.post("/items", json=bad_branch, headers=HEADERS).status_code == 422
    assert client.post("/items", json=bad_email, headers=HEADERS).status_code == 422

    created = client.post("/items", json=payload, headers=HEADERS)
    assert created.status_code == 201
    duplicate = client.post("/items", json=payload, headers=HEADERS)
    assert duplicate.status_code == 409


def test_responses_omit_notes(client: TestClient) -> None:
    add_item(client, item_id="BP-NOTE", expiry_date=date(2026, 11, 1), source_row=9)
    listed = client.get("/items", headers=HEADERS)
    expiring = client.get("/items/expiring", headers=HEADERS)
    assert listed.status_code == 200
    assert expiring.status_code == 200
    assert "notes" not in listed.json()[0]
    assert "notes" not in expiring.json()[0]
    assert "P7730215" not in listed.text
    assert "P7730215" not in expiring.text
