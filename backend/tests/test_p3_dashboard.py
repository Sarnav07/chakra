"""P3 dashboard tests (SPEC 14, 19 T11)."""
import json

import pytest

from app.db import get_conn, get_meta, now_iso


EXPECTED_KEYS = {"scenario", "fill_trend", "forecast", "plan",
                 "pickups", "reports", "batches", "mess"}


def _walk_strings(obj):
    """Yield every key and string value in a nested structure."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_strings(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_strings(item)
    elif isinstance(obj, str):
        yield obj


def test_top_level_keys(seeded_client):
    r = seeded_client.get("/api/dashboard")
    assert r.status_code == 200
    assert set(r.json().keys()) == EXPECTED_KEYS


def test_no_recycled_or_composted(seeded_client):
    """T11: no key or string value contains 'recycled' or 'composted'."""
    r = seeded_client.get("/api/dashboard")
    data = r.json()
    for s in _walk_strings(data):
        low = s.lower()
        assert "recycled" not in low, f"Found 'recycled' in: {s}"
        assert "composted" not in low, f"Found 'composted' in: {s}"


def test_fresh_seed_shape(seeded_client):
    r = seeded_client.get("/api/dashboard")
    assert r.status_code == 200
    data = r.json()

    assert data["plan"] is None
    assert data["pickups"]["live_total"] == 0
    assert 1 <= len(data["fill_trend"]) <= 14
    assert data["mess"]["last7_total_kg"] > 0


def test_forecast_present_after_run(seeded_client):
    seeded_client.post("/api/forecasts", json={})
    r = seeded_client.get("/api/dashboard")
    data = r.json()
    fc = data["forecast"]
    assert fc is not None
    assert 0 <= fc["mean_p_overflow"] <= 1


def test_plan_and_pickups_after_commit(seeded_client, seeded_db_path):
    """After inserting a test plan and confirming a pickup, dashboard reflects them."""
    conn = get_conn(seeded_db_path)
    plan_date = get_meta(conn, "plan_date")
    now = now_iso()

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

    pickup_r = seeded_client.post("/api/pickups", json={
        "route_id": "P-TEST-V1", "bin_id": "HA-1", "level": "full",
    })
    assert pickup_r.status_code == 200

    r = seeded_client.get("/api/dashboard")
    data = r.json()

    assert data["plan"] is not None
    assert data["pickups"]["live_total"] == 1
    assert data["pickups"]["today"] == 1
    assert data["batches"]["pending_handoff_l"] > 0


def test_plan_km_with_real_routes(seeded_client):
    """If /api/routes is real and has recommended_fleet_size, commit and check km."""
    routes_r = seeded_client.post("/api/routes", json={"tau": 0.5})
    if routes_r.status_code != 200:
        pytest.skip("routes endpoint not available")
    routes_data = routes_r.json()
    if routes_data.get("mock"):
        pytest.skip("routes endpoint is still a mock")
    rec = routes_data.get("recommended_fleet_size")
    if rec is None:
        pytest.skip("recommended_fleet_size is null")

    plan_id = routes_data["plan_id"]
    choose_r = seeded_client.post(f"/api/routes/{plan_id}/choose",
                                  json={"fleet_size": rec})
    assert choose_r.status_code == 200

    r = seeded_client.get("/api/dashboard")
    data = r.json()
    assert data["plan"] is not None
    assert isinstance(data["plan"]["km"], (int, float))
