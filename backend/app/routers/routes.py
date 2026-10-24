"""Route plans, plan choice and worker routes (owner P2, SPEC Section 14)."""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException

from app import config
from app.db import get_db, now_iso
from app.reports.service import mark_in_plan
from app.routing.plan import baseline_nearest_neighbor, plan_routes
from app.routing.types import Stop
from app.schemas import ChooseIn, RoutesIn
from app.selection.select import decide

router = APIRouter(tags=["routes"])

BASELINE_FLEET_IF_NONE = 2   # SPEC 10: baseline uses k=2 if no alternative is feasible


def _savings(recommended: dict | None, baseline: dict) -> dict | None:
    """Simulated savings of the recommended alternative vs the baseline."""
    if recommended is None or baseline["total_km"] == 0:
        return None
    km = baseline["total_km"] - recommended["total_km"]
    return {"km": km,
            "km_pct": round(km / baseline["total_km"] * 100, 1),
            "cost_rs": baseline["total_cost_rs"] - recommended["total_cost_rs"]}


def _public(response: dict) -> dict:
    """The stored response without the full decisions list."""
    return {k: v for k, v in response.items() if k != "decisions"}


def _load_plan(conn, plan_id: str):
    row = conn.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Unknown plan")
    return row


@router.post("/routes")
def create_routes(body: RoutesIn, conn=Depends(get_db)):
    try:
        decided = decide(conn, body.tau)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from None
    selected = [d for d in decided["decisions"] if d["selected"]]
    stops = [Stop(bin_id=d["bin_id"], name=d["name"], lat=d["lat"], lon=d["lon"],
                  stream=d["stream"], demand_l=d["demand_l"]) for d in selected]
    planned = plan_routes(stops, fleet_sizes=tuple(body.fleet_sizes), fast=body.fast)
    rec_size = planned["recommended_fleet_size"]
    recommended = next((a for a in planned["alternatives"] if a["fleet_size"] == rec_size), None)
    baseline = {"method": "nearest_neighbor",
                **baseline_nearest_neighbor(stops, rec_size or BASELINE_FLEET_IF_NONE)}

    plan_date = decided["plan_date"]
    plan_id = f"P-{plan_date}-{uuid.uuid4().hex[:6]}"
    response = {
        "plan_id": plan_id,
        "plan_date": plan_date,
        "tau": decided["tau"],
        "decisions_summary": decided["summary"],
        "selected_bin_ids": [d["bin_id"] for d in selected],
        "alternatives": planned["alternatives"],
        "recommended_fleet_size": rec_size,
        "baseline": baseline,
        "savings_vs_baseline": _savings(recommended, baseline),
        "assumptions": config.scenario_assumptions(),
        "synthetic": True,
        "decisions": decided["decisions"],
    }
    conn.execute(
        "INSERT INTO plans (plan_id, plan_date, tau, created_at, chosen_fleet_size, status, "
        "response_json) VALUES (?, ?, ?, ?, NULL, 'draft', ?)",
        (plan_id, plan_date, decided["tau"], now_iso(), json.dumps(response, allow_nan=False)))
    conn.commit()
    return _public(response)


@router.get("/routes/{plan_id}")
def get_plan(plan_id: str, conn=Depends(get_db)):
    return _public(json.loads(_load_plan(conn, plan_id)["response_json"]))


@router.post("/routes/{plan_id}/choose")
def choose_plan(plan_id: str, body: ChooseIn, conn=Depends(get_db)):
    plan = _load_plan(conn, plan_id)
    if plan["status"] != "draft":
        raise HTTPException(409, f"Plan is already {plan['status']}")
    response = json.loads(plan["response_json"])
    alt = next((a for a in response["alternatives"] if a["fleet_size"] == body.fleet_size), None)
    if alt is None:
        raise HTTPException(404, f"No alternative with fleet_size {body.fleet_size} in this plan")
    if not alt["feasible"]:
        raise HTTPException(409, "This alternative is infeasible - manual dispatch required")

    now = now_iso()
    route_ids = [f"{plan_id}-{r['vehicle_id']}" for r in alt["routes"]]
    try:
        conn.execute("UPDATE plans SET status = 'superseded' WHERE status = 'committed' "
                     "AND plan_date = ? AND plan_id != ?", (plan["plan_date"], plan_id))
        for route_id, r in zip(route_ids, alt["routes"]):
            conn.execute(
                "INSERT INTO route_plans (route_id, plan_id, fleet_size, vehicle_id, stream, "
                "start_node, end_node, ordered_bin_ids, km, minutes, load_l, est_cost_rs, "
                "feasible) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (route_id, plan_id, body.fleet_size, r["vehicle_id"], r["stream"],
                 r["start_node"], r["end_node"], json.dumps(r["ordered_bin_ids"]),
                 r["km"], r["minutes"], r["load_l"], r["est_cost_rs"], int(alt["feasible"])))
        for d in response["decisions"]:
            # decide() does not return forecast ids, so forecast_id stays NULL
            conn.execute(
                "INSERT INTO pickup_decisions (plan_id, plan_date, bin_id, tau, selected, "
                "reason_code, reason, p_overflow, forecast_id, report_id, missed, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, 0, ?)",
                (plan_id, plan["plan_date"], d["bin_id"], plan["tau"], int(d["selected"]),
                 d["reason_code"], d["reason"], d["p_overflow"], d["report_id"], now))
        conn.execute("UPDATE plans SET status = 'committed', chosen_fleet_size = ? "
                     "WHERE plan_id = ?", (body.fleet_size, plan_id))
        # mark_in_plan commits, so it runs last and closes the one transaction
        mark_in_plan(conn, [d["bin_id"] for d in response["decisions"]
                            if d["selected"] and d["reason_code"] == "reported"])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"plan_id": plan_id, "status": "committed", "route_ids": route_ids}


def _food_batches_delivered(conn, pickup_ids: set[int]) -> bool:
    """True if the route has food batches and every one is delivered_to_compost."""
    statuses = [b["status"] for b in conn.execute(
        "SELECT source_pickup_ids, status FROM batch_events WHERE stream = 'food'")
        if set(json.loads(b["source_pickup_ids"])) & pickup_ids]
    return bool(statuses) and all(s == "delivered_to_compost" for s in statuses)


@router.get("/worker/routes")
def worker_routes(conn=Depends(get_db)):
    plan = conn.execute("SELECT plan_id, plan_date FROM plans WHERE status = 'committed' "
                        "ORDER BY created_at DESC, rowid DESC LIMIT 1").fetchone()
    if plan is None:
        raise HTTPException(404, "No committed plan yet - choose a plan on Plan tomorrow")
    bins = {b["bin_id"]: b for b in conn.execute("SELECT bin_id, name, lat, lon FROM bins")}
    routes = []
    for r in conn.execute("SELECT * FROM route_plans WHERE plan_id = ? ORDER BY route_id",
                          (plan["plan_id"],)).fetchall():
        pickups = {p["bin_id"]: p for p in conn.execute(
            "SELECT pickup_id, bin_id, completed_at FROM pickup_events WHERE route_id = ?",
            (r["route_id"],))}
        stops = []
        for seq, bin_id in enumerate(json.loads(r["ordered_bin_ids"]), start=1):
            b, p = bins[bin_id], pickups.get(bin_id)
            stops.append({"seq": seq, "bin_id": bin_id, "name": b["name"], "lat": b["lat"],
                          "lon": b["lon"], "done": p is not None,
                          "completed_at": p["completed_at"] if p else None})
        all_done = all(s["done"] for s in stops)
        compost_delivered = (r["stream"] == "food" and all_done and _food_batches_delivered(
            conn, {p["pickup_id"] for p in pickups.values()}))
        routes.append({"route_id": r["route_id"], "vehicle_id": r["vehicle_id"],
                       "stream": r["stream"], "end_node": r["end_node"], "stops": stops,
                       "all_done": all_done, "compost_delivered": compost_delivered})
    return {"plan_id": plan["plan_id"], "plan_date": plan["plan_date"], "routes": routes}
