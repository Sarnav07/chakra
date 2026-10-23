"""P2 core tests: health, scenario, schema, endpoint contract, report helpers."""
import pytest

from app.db import set_meta
from app.main import app
from app.reports.service import active_reports_by_bin, mark_in_plan, mark_resolved

TABLES = {"meta", "bins", "nodes", "vehicles", "fill_observations", "fill_forecasts",
          "plans", "route_plans", "pickup_decisions", "pickup_events", "batch_events",
          "overflow_reports", "item_checks", "mess_waste_logs"}

# every endpoint of SPEC Section 14
SPEC_ENDPOINTS = {
    ("GET", "/api/health"), ("GET", "/api/scenario"), ("POST", "/api/demo/reset"),
    ("GET", "/api/bins"), ("GET", "/api/bins/{bin_id}/history"),
    ("POST", "/api/observations"), ("POST", "/api/forecasts"),
    ("GET", "/api/forecasts/latest"), ("GET", "/api/forecasts/eval"),
    ("POST", "/api/decisions"), ("GET", "/api/twin"), ("POST", "/api/twin/run"),
    ("GET", "/api/classify/status"), ("POST", "/api/classify"),
    ("POST", "/api/routes"), ("GET", "/api/routes/{plan_id}"),
    ("POST", "/api/routes/{plan_id}/choose"), ("GET", "/api/worker/routes"),
    ("POST", "/api/reports"), ("GET", "/api/reports"),
    ("POST", "/api/reports/{report_id}/reject"),
    ("GET", "/api/scale-lab"), ("POST", "/api/scale-lab/run"),
    ("POST", "/api/pickups"), ("POST", "/api/pickups/arrive-compost"), ("GET", "/api/batches"),
    ("POST", "/api/mess-logs"), ("GET", "/api/mess-logs"), ("GET", "/api/dashboard"),
}

# GET endpoints and the status codes SPEC 14 allows for them
GET_PATHS = {
    "/api/health": {200},
    "/api/scenario": {200, 404},
    "/api/bins": {200},
    "/api/bins/HA-1/history": {200, 404},
    "/api/forecasts/latest": {200, 404},
    "/api/forecasts/eval": {200},
    "/api/twin": {200, 404},
    "/api/classify/status": {200},
    "/api/routes/P-2026-10-25-abc123": {200, 404},
    "/api/worker/routes": {200, 404},
    "/api/reports": {200},
    "/api/reports?status=all": {200},
    "/api/scale-lab": {200, 404},
    "/api/batches": {200},
    "/api/mess-logs": {200},
    "/api/dashboard": {200},
}


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_scenario_404_on_empty_db(client):
    r = client.get("/api/scenario")
    assert r.status_code == 404
    assert r.json() == {"detail": "Database not seeded - run python -m app.seed"}


def test_scenario_reads_meta(client, conn):
    for key, value in {"scenario_date": "2026-10-24", "plan_date": "2026-10-25",
                       "scenario_now": "2026-10-24T20:30:00+05:30", "seed": 42}.items():
        set_meta(conn, key, value)
    body = client.get("/api/scenario").json()
    assert body["plan_date"] == "2026-10-25"
    assert body["seed"] == 42
    assert body["synthetic"] is True
    assert body["timezone"] == "UTC+05:30 (IST)"
    assert set(body["assumptions"]) == {
        "detour_factor", "speed_kmph", "service_min_per_bin", "shift_min", "capacity_buffer",
        "level_pct", "stale_hours", "food_density_kg_per_l", "tau_default", "tau_min",
        "tau_max"}


def test_all_tables_exist(conn):
    names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert len(TABLES) == 14
    assert TABLES <= names


def test_every_spec_endpoint_is_registered():
    # read the public OpenAPI schema: newer FastAPI nests included routers in app.routes
    registered = {(method.upper(), path) for path, ops in app.openapi()["paths"].items()
                  for method in ops}
    assert SPEC_ENDPOINTS - registered == set()


@pytest.mark.parametrize("path, allowed", GET_PATHS.items())
def test_get_endpoints_no_500(client, path, allowed):
    assert client.get(path).status_code in allowed


def test_request_validation(client):
    assert client.post("/api/decisions", json={"tau": 0.01}).status_code == 422
    assert client.post("/api/observations",
                       json={"bin_id": "HA-1", "level": "low", "fill_pct": 20}).status_code == 422
    assert client.post("/api/reports", data={"bin_id": "HA-1", "kind": "spill",
                                             "reporter_role": "qr"}).status_code == 422
    # empty test database: HA-1 does not exist -> 404 unknown bin
    assert client.post("/api/reports", data={"bin_id": "HA-1", "kind": "overflow",
                                             "reporter_role": "qr"}).status_code == 404
    assert client.post("/api/classify", data={"bin_id": "HA-1"}).status_code == 503


def test_reports_service_lifecycle(conn):
    conn.execute("INSERT INTO bins VALUES ('HA-1', 'Hostel A bin 1', 'hostel', 'Hostel A', "
                 "'general', 29.866, 77.894, 240)")
    conn.execute("INSERT INTO overflow_reports (bin_id, kind, reported_at, updated_at, "
                 "reporter_role, status, verified) VALUES ('HA-1', 'overflow', "
                 "'2026-10-24T18:00:00+05:30', '2026-10-24T18:00:00+05:30', 'qr', 'open', 0)")
    conn.commit()
    assert active_reports_by_bin(conn)["HA-1"]["status"] == "open"
    mark_in_plan(conn, ["HA-1"])
    assert active_reports_by_bin(conn)["HA-1"]["status"] == "in_plan"
    assert mark_resolved(conn, "HA-1") == 1
    assert active_reports_by_bin(conn) == {}
