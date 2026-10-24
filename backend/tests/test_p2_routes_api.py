"""P2 routes API: POST /routes, GET /routes/{id}, choose, worker routes (T4, T5, T7)."""
from collections import Counter

from app.routing.feasibility import check_alternative
from app.routing.types import RoutingSettings

ALT_KEYS = {"fleet_size", "feasible", "manual_dispatch_required", "total_km",
            "completion_minutes", "total_minutes", "total_cost_rs", "vehicles_used",
            "unassigned_bin_ids", "routes"}
ROUTE_KEYS = {"vehicle_id", "stream", "start_node", "end_node", "stops", "ordered_bin_ids",
              "km", "minutes", "load_l", "est_cost_rs", "solver", "polyline"}
PLAN_KEYS = {"plan_id", "plan_date", "tau", "decisions_summary", "selected_bin_ids",
             "alternatives", "recommended_fleet_size", "baseline", "savings_vs_baseline",
             "assumptions", "synthetic"}


def _post(client, **body):
    r = client.post("/api/routes", json={"tau": 0.5, "fast": True, **body})
    assert r.status_code == 200, r.text
    return r.json()


def _choose(client, plan_id, fleet_size):
    return client.post(f"/api/routes/{plan_id}/choose", json={"fleet_size": fleet_size})


def _placed(alt):
    return [b for r in alt["routes"] for b in r["ordered_bin_ids"]] + alt["unassigned_bin_ids"]


def test_routes_404_on_empty_db(client):
    r = client.post("/api/routes", json={"tau": 0.5})
    assert r.status_code == 404
    assert r.json() == {"detail": "Database not seeded - run python -m app.seed"}


def test_unknown_plan_404(seeded_client):
    assert seeded_client.get("/api/routes/P-2026-10-25-nope00").status_code == 404
    assert _choose(seeded_client, "P-2026-10-25-nope00", 2).status_code == 404


def test_worker_routes_404_before_commit(seeded_client):
    r = seeded_client.get("/api/worker/routes")
    assert r.status_code == 404
    assert r.json() == {"detail": "No committed plan yet - choose a plan on Plan tomorrow"}


def test_post_routes_contract(seeded_client):
    plan = _post(seeded_client)
    assert set(plan) == PLAN_KEYS          # no "mock", no "decisions"
    assert plan["plan_id"].startswith(f"P-{plan['plan_date']}-")
    assert plan["synthetic"] is True
    assert plan["selected_bin_ids"]
    assert len(plan["alternatives"]) >= 1
    selected = Counter(plan["selected_bin_ids"])
    for alt in plan["alternatives"]:
        assert set(alt) == ALT_KEYS
        for route in alt["routes"]:
            assert set(route) == ROUTE_KEYS
        # T4: every selected bin is in exactly one route or unassigned
        assert Counter(_placed(alt)) == selected

    # T5: baseline has the recommended fleet size (2 if none) and the same stop set
    baseline = plan["baseline"]
    assert baseline["method"] == "nearest_neighbor"
    assert ALT_KEYS <= set(baseline)
    assert baseline["fleet_size"] == (plan["recommended_fleet_size"] or 2)
    assert Counter(_placed(baseline)) == selected

    savings = plan["savings_vs_baseline"]
    if plan["recommended_fleet_size"] is None or baseline["total_km"] == 0:
        assert savings is None
    else:
        rec = next(a for a in plan["alternatives"]
                   if a["fleet_size"] == plan["recommended_fleet_size"])
        assert savings["km"] == baseline["total_km"] - rec["total_km"]
        assert savings["km_pct"] == round(savings["km"] / baseline["total_km"] * 100, 1)

    # GET returns the stored response
    assert seeded_client.get(f"/api/routes/{plan['plan_id']}").json() == plan


def test_choose_infeasible_409(seeded_client):
    plan = _post(seeded_client, fleet_sizes=[1])
    alt = plan["alternatives"][0]
    if alt["feasible"]:
        # the seed has no infeasible k=1 plan: test the gate directly instead
        broken = {**alt, "unassigned_bin_ids": [plan["selected_bin_ids"][0]]}
        assert check_alternative(broken, plan["selected_bin_ids"], RoutingSettings())
        return
    r = _choose(seeded_client, plan["plan_id"], 1)
    assert r.status_code == 409
    assert r.json() == {"detail": "This alternative is infeasible - manual dispatch required"}
    assert seeded_client.get("/api/worker/routes").status_code == 404


def test_choose_commits_and_second_plan_supersedes(seeded_client, seeded_db_path):
    from app.db import get_conn

    first = _post(seeded_client)
    k = first["recommended_fleet_size"]
    assert k is not None, "seed should have a feasible alternative"
    r = _choose(seeded_client, first["plan_id"], k)
    assert r.status_code == 200, r.text
    alt = next(a for a in first["alternatives"] if a["fleet_size"] == k)
    assert r.json() == {"plan_id": first["plan_id"], "status": "committed",
                        "route_ids": [f"{first['plan_id']}-{x['vehicle_id']}"
                                      for x in alt["routes"]]}
    assert _choose(seeded_client, first["plan_id"], k).status_code == 409

    worker = seeded_client.get("/api/worker/routes").json()
    assert worker["plan_id"] == first["plan_id"]
    assert [w["route_id"] for w in worker["routes"]] == r.json()["route_ids"]
    for w, route in zip(worker["routes"], alt["routes"]):
        assert [s["bin_id"] for s in w["stops"]] == route["ordered_bin_ids"]
        assert all(s["done"] is False and s["completed_at"] is None for s in w["stops"])
        assert w["all_done"] is False and w["compost_delivered"] is False
        assert w["end_node"] == ("COMPOST" if w["stream"] == "food" else "DEPOT")

    conn = get_conn(seeded_db_path)
    try:
        n_bins = conn.execute("SELECT COUNT(*) FROM bins").fetchone()[0]
        rows = conn.execute("SELECT bin_id, selected FROM pickup_decisions WHERE plan_id = ?",
                            (first["plan_id"],)).fetchall()
        assert len(rows) == n_bins
        assert sorted(r["bin_id"] for r in rows if r["selected"]) == sorted(
            first["selected_bin_ids"])
        assert conn.execute("SELECT COUNT(*) FROM route_plans WHERE plan_id = ?",
                            (first["plan_id"],)).fetchone()[0] == len(alt["routes"])

        second = _post(seeded_client)
        assert _choose(seeded_client, second["plan_id"],
                       second["recommended_fleet_size"]).status_code == 200
        status = dict(conn.execute("SELECT plan_id, status FROM plans").fetchall())
        assert status == {first["plan_id"]: "superseded", second["plan_id"]: "committed"}
    finally:
        conn.close()
    assert seeded_client.get("/api/worker/routes").json()["plan_id"] == second["plan_id"]
