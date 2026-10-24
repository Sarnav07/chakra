"""Dashboard reads only persisted plan and live handoff data."""


def test_dashboard_seed_then_live_pickup(seeded_client):
    first = seeded_client.get("/api/dashboard")
    assert first.status_code == 200
    data = first.json()
    assert set(data) == {"scenario", "fill_trend", "forecast", "plan", "pickups",
                         "reports", "batches", "mess"}
    assert data["plan"] is None
    assert data["pickups"]["live_total"] == 0
    assert "composted" not in str(data).lower()
    plan = seeded_client.post("/api/routes", json={"tau": 0.5, "fast": True}).json()
    assert plan["recommended_fleet_size"] is not None
    seeded_client.post(f"/api/routes/{plan['plan_id']}/choose",
                       json={"fleet_size": plan["recommended_fleet_size"]})
    route = seeded_client.get("/api/worker/routes").json()["routes"][0]
    seeded_client.post("/api/pickups", json={
        "route_id": route["route_id"], "bin_id": route["stops"][0]["bin_id"]})
    updated = seeded_client.get("/api/dashboard").json()
    assert updated["plan"]["plan_id"] == plan["plan_id"]
    assert updated["pickups"]["live_total"] == 1
    assert updated["batches"]["pending_handoff_l"] >= 0
