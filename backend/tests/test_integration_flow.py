"""One seeded API journey across selection, routing, reporting and handoff."""


def test_reported_skipped_bin_is_collected(seeded_client):
    decisions = seeded_client.post("/api/decisions", json={"tau": 0.5}).json()["decisions"]
    skipped = next(row for row in decisions if row["reason_code"] == "below_tau")
    response = seeded_client.post("/api/reports", data={
        "bin_id": skipped["bin_id"], "kind": "overflow", "reporter_role": "staff"})
    assert response.status_code == 200, response.text
    report_id = response.json()["report"]["report_id"]

    plan_response = seeded_client.post("/api/routes", json={"tau": 0.5, "fast": True})
    assert plan_response.status_code == 200, plan_response.text
    plan = plan_response.json()
    assert skipped["bin_id"] in plan["selected_bin_ids"]
    assert plan["recommended_fleet_size"] is not None
    chosen = seeded_client.post(f"/api/routes/{plan['plan_id']}/choose",
                                json={"fleet_size": plan["recommended_fleet_size"]})
    assert chosen.status_code == 200, chosen.text
    reports = seeded_client.get("/api/reports", params={"status": "in_plan"}).json()["reports"]
    assert any(row["report_id"] == report_id for row in reports)

    worker = seeded_client.get("/api/worker/routes").json()
    route = next(route for route in worker["routes"]
                 if any(stop["bin_id"] == skipped["bin_id"] for stop in route["stops"]))
    pickup = seeded_client.post("/api/pickups", json={
        "route_id": route["route_id"], "bin_id": skipped["bin_id"]})
    assert pickup.status_code == 200, pickup.text
    assert pickup.json()["batch"]["status"] == "pending_handoff"
    resolved = seeded_client.get("/api/reports", params={"status": "resolved"}).json()["reports"]
    assert any(row["report_id"] == report_id for row in resolved)
    dashboard = seeded_client.get("/api/dashboard").json()
    assert dashboard["pickups"]["live_total"] == 1
    assert dashboard["plan"]["plan_id"] == plan["plan_id"]
    assert "mock" not in str(dashboard)
