"""P3 pickup, batch and compost tests (SPEC 19 T9, T10)."""
import json

import pytest

from app.db import get_meta, now_iso


@pytest.fixture
def plan_client(seeded_client, seeded_db_path):
    """Insert a committed plan with two routes so pickup tests work."""
    from app.db import get_conn

    conn = get_conn(seeded_db_path)
    plan_date = get_meta(conn, "plan_date")
    now = now_iso()

    for bid in ("HA-1", "HA-2", "M1-F1", "M1-F2"):
        assert conn.execute("SELECT 1 FROM bins WHERE bin_id = ?", (bid,)).fetchone(), \
            f"{bid} missing from seeded db"

    conn.execute(
        "INSERT INTO plans (plan_id, plan_date, tau, created_at, chosen_fleet_size, "
        "status, response_json) VALUES (?, ?, 0.5, ?, 2, 'committed', '{}')",
        ("P-TEST", plan_date, now),
    )
    conn.execute(
        "INSERT INTO route_plans (route_id, plan_id, fleet_size, vehicle_id, stream, "
        "start_node, end_node, ordered_bin_ids, km, minutes, load_l, est_cost_rs, feasible) "
        "VALUES (?, 'P-TEST', 2, 'V1', 'general', 'DEPOT', 'DEPOT', ?, 1.0, 10.0, 100.0, 812.0, 1)",
        ("P-TEST-V1", json.dumps(["HA-1", "HA-2"])),
    )
    conn.execute(
        "INSERT INTO route_plans (route_id, plan_id, fleet_size, vehicle_id, stream, "
        "start_node, end_node, ordered_bin_ids, km, minutes, load_l, est_cost_rs, feasible) "
        "VALUES (?, 'P-TEST', 2, 'V2', 'food', 'DEPOT', 'COMPOST', ?, 1.0, 10.0, 100.0, 812.0, 1)",
        ("P-TEST-V2", json.dumps(["M1-F1", "M1-F2"])),
    )
    conn.commit()
    conn.close()
    return seeded_client


def test_confirm_pickup_happy(plan_client):
    """T9: confirm creates exactly one pickup, one batch, one pickup_reset observation."""
    r = plan_client.post("/api/pickups", json={
        "route_id": "P-TEST-V1", "bin_id": "HA-1", "level": "full",
    })
    assert r.status_code == 200
    data = r.json()

    pickup = data["pickup"]
    assert pickup["route_id"] == "P-TEST-V1"
    assert pickup["bin_id"] == "HA-1"
    assert pickup["level"] == "full"
    assert pickup["collected_volume_l"] == 240 * 90 / 100  # full=90%, capacity=240

    batch = data["batch"]
    assert batch["destination"] == "depot"
    assert batch["status"] == "pending_handoff"
    assert batch["volume_l"] == 240 * 90 / 100
    assert json.loads(batch["source_pickup_ids"]) == [pickup["pickup_id"]]

    r2 = plan_client.get("/api/bins/HA-1/history?days=1")
    obs = r2.json()["observations"]
    reset = [o for o in obs if o["source"] == "pickup_reset"]
    assert len(reset) >= 1
    assert reset[-1]["fill_pct"] == 0


def test_confirm_pickup_duplicate(plan_client):
    """T9: second confirmation for the same (route, bin) -> 409."""
    plan_client.post("/api/pickups", json={
        "route_id": "P-TEST-V1", "bin_id": "HA-1", "level": "full",
    })
    r = plan_client.post("/api/pickups", json={
        "route_id": "P-TEST-V1", "bin_id": "HA-1", "level": "full",
    })
    assert r.status_code == 409
    assert "already confirmed" in r.json()["detail"].lower()


def test_confirm_wrong_bin(plan_client):
    """HA-3 is not on P-TEST-V1 -> 400."""
    r = plan_client.post("/api/pickups", json={
        "route_id": "P-TEST-V1", "bin_id": "HA-3",
    })
    assert r.status_code == 400


def test_confirm_unknown_route(plan_client):
    """Route "NOPE" does not exist -> 404."""
    r = plan_client.post("/api/pickups", json={
        "route_id": "NOPE", "bin_id": "HA-1",
    })
    assert r.status_code == 404


def test_confirm_bad_level(plan_client):
    """Level "huge" is invalid -> 422 from Pydantic."""
    r = plan_client.post("/api/pickups", json={
        "route_id": "P-TEST-V1", "bin_id": "HA-1", "level": "huge",
    })
    assert r.status_code == 422


def test_arrive_compost_not_food(plan_client):
    """Arrive-compost on a general route -> 400."""
    r = plan_client.post("/api/pickups/arrive-compost", json={
        "route_id": "P-TEST-V1",
    })
    assert r.status_code == 400


def test_arrive_compost_not_all_confirmed(plan_client):
    """Arrive-compost with only one food stop confirmed -> 409."""
    plan_client.post("/api/pickups", json={
        "route_id": "P-TEST-V2", "bin_id": "M1-F1", "level": "medium",
    })
    r = plan_client.post("/api/pickups/arrive-compost", json={
        "route_id": "P-TEST-V2",
    })
    assert r.status_code == 409


def test_arrive_compost_happy(plan_client):
    """T10: all food stops confirmed -> arrive-compost succeeds."""
    plan_client.post("/api/pickups", json={
        "route_id": "P-TEST-V2", "bin_id": "M1-F1", "level": "medium",
    })
    plan_client.post("/api/pickups", json={
        "route_id": "P-TEST-V2", "bin_id": "M1-F2", "level": "full",
    })
    r = plan_client.post("/api/pickups/arrive-compost", json={
        "route_id": "P-TEST-V2",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["delivered_batches"] == 2

    batches_r = plan_client.get("/api/batches?status=delivered_to_compost")
    batches = batches_r.json()["batches"]
    for b in batches:
        assert b["destination"] == "compost_stop"
        assert b["status"] == "delivered_to_compost"


def test_list_batches_all(plan_client):
    """GET /api/batches?status=all returns totals matching the rows."""
    plan_client.post("/api/pickups", json={
        "route_id": "P-TEST-V1", "bin_id": "HA-1", "level": "full",
    })
    plan_client.post("/api/pickups", json={
        "route_id": "P-TEST-V1", "bin_id": "HA-2", "level": "low",
    })
    r = plan_client.get("/api/batches?status=all")
    assert r.status_code == 200
    data = r.json()
    assert len(data["batches"]) == 2
    total_vol = sum(b["volume_l"] for b in data["batches"])
    totals_vol = sum(t["volume_l"] for t in data["totals"])
    assert abs(total_vol - totals_vol) < 0.01


def test_list_batches_bad_status(plan_client):
    """GET /api/batches?status=bogus -> 422."""
    r = plan_client.get("/api/batches?status=bogus")
    assert r.status_code == 422
