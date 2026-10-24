"""P3 mess food-waste log tests."""
import pytest


VALID_LOG = {
    "mess_id": "Jawahar Bhawan Mess",
    "meal": "lunch",
    "category": "plate",
    "weight_kg": 12.5,
    "weighed": True,
}


def test_create_log_happy(seeded_client):
    """Valid log -> 200 with source 'staff'."""
    r = seeded_client.post("/api/mess-logs", json=VALID_LOG)
    assert r.status_code == 200
    log = r.json()["log"]
    assert log["source"] == "staff"
    assert log["mess_id"] == "Jawahar Bhawan Mess"
    assert log["meal"] == "lunch"
    assert log["category"] == "plate"
    assert log["weight_kg"] == 12.5
    assert log["weighed"] == 1


def test_create_log_unknown_mess(seeded_client):
    """'Mess 9' does not exist -> 422."""
    body = {**VALID_LOG, "mess_id": "Mess 9"}
    r = seeded_client.post("/api/mess-logs", json=body)
    assert r.status_code == 422


def test_create_log_weight_zero(seeded_client):
    """weight_kg=0 -> 422 (Pydantic gt=0)."""
    body = {**VALID_LOG, "weight_kg": 0}
    r = seeded_client.post("/api/mess-logs", json=body)
    assert r.status_code == 422


def test_create_log_weight_over_500(seeded_client):
    """weight_kg=501 -> 422 (Pydantic le=500)."""
    body = {**VALID_LOG, "weight_kg": 501}
    r = seeded_client.post("/api/mess-logs", json=body)
    assert r.status_code == 422


def test_create_log_bad_meal(seeded_client):
    """meal='brunch' -> 422 (Pydantic Literal)."""
    body = {**VALID_LOG, "meal": "brunch"}
    r = seeded_client.post("/api/mess-logs", json=body)
    assert r.status_code == 422


def test_list_logs_has_daily_and_by_meal(seeded_client):
    """GET returns daily, by_meal, and synthetic_rows > 0 from seed data."""
    r = seeded_client.get("/api/mess-logs")
    assert r.status_code == 200
    data = r.json()
    assert "daily" in data
    assert "by_meal" in data
    assert data["synthetic_rows"] > 0


def test_list_logs_after_staff_post(seeded_client):
    """After posting a staff log, staff_rows >= 1."""
    seeded_client.post("/api/mess-logs", json=VALID_LOG)
    r = seeded_client.get("/api/mess-logs")
    assert r.status_code == 200
    data = r.json()
    assert data["staff_rows"] >= 1
