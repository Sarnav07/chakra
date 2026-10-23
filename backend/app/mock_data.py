"""Temporary mock responses for stub endpoints (owner P2).

Shapes follow SPEC Section 14 exactly and every response has "mock": true.
Values are placeholders for UI development only - they are NOT results.
Derived numbers (km, minutes, costs, counts, totals) are computed from the
mock inputs below. Owners delete their use of this file when they replace
a stub router with real code.
"""
import math
import uuid
from datetime import date, datetime, time, timedelta

from app.config import (CAMPUS_CENTER, CAPACITY_BUFFER, DEFAULT_TAU, DETOUR_FACTOR,
                        LEVEL_PCT, MIN_DEMAND_PCT, NODES, OVERFLOW_PCT,
                        SERVICE_MIN_PER_BIN, SHIFT_MIN, SPEED_KMPH, STALE_HOURS, TZ,
                        VEHICLES, scenario_assumptions)
from app.db import now_iso

MOCK_SCENARIO_DATE = date(2026, 10, 24)
MOCK_PLAN_DATE = MOCK_SCENARIO_DATE + timedelta(days=1)
MOCK_NOW = datetime.combine(MOCK_SCENARIO_DATE, time(20, 30), tzinfo=TZ)
MOCK_VERSION = "mock"
MOCK_PLAN_ID = f"P-{MOCK_PLAN_DATE}-000000"
MOCK_FLEET_SIZES = (1, 2)   # the mock plan always offers these two alternatives


def _ts(days_before: int, hour: int, minute: int = 0) -> str:
    day = MOCK_SCENARIO_DATE - timedelta(days=days_before)
    return datetime.combine(day, time(hour, minute), tzinfo=TZ).isoformat()


def _bin(bin_id, name, group_type, group_name, stream, dlat, dlon, capacity_l):
    return {"bin_id": bin_id, "name": name, "group_type": group_type,
            "group_name": group_name, "stream": stream,
            "lat": round(CAMPUS_CENTER[0] + dlat, 6),
            "lon": round(CAMPUS_CENTER[1] + dlon, 6), "capacity_l": capacity_l}


MOCK_BINS = [
    _bin("HA-1", "Hostel A bin 1", "hostel", "Hostel A", "general", 0.0012, -0.0018, 240),
    _bin("HB-1", "Hostel B bin 1", "hostel", "Hostel B", "general", 0.0024, 0.0008, 240),
    _bin("M1-G1", "Mess 1 general bin 1", "mess", "Mess 1", "general", -0.0005, 0.0021, 660),
    _bin("M1-F1", "Mess 1 food bin 1", "mess_food", "Mess 1", "food", -0.0003, 0.0024, 120),
    _bin("D1-1", "Dept 1 bin 1", "department", "Dept 1", "general", -0.0017, -0.0005, 120),
    _bin("D2-1", "Dept 2 bin 1", "department", "Dept 2", "general", 0.0040, -0.0035, 120),
]
BINS_BY_ID = {b["bin_id"]: b for b in MOCK_BINS}

# bin_id: (latest fill %, days since the latest 20:00 reading, increment p10, p50, p90)
_READINGS = {
    "HA-1": (80, 0, 15, 22, 30),
    "HB-1": (100, 0, 18, 25, 33),
    "M1-G1": (40, 0, 20, 28, 36),
    "M1-F1": (75, 0, 25, 32, 40),
    "D1-1": (35, 3, 8, 12, 16),     # stale -> needs_review
    "D2-1": (30, 0, 6, 10, 14),     # has an open report
}

_REPORTS = [
    {"report_id": 1, "bin_id": "D2-1", "kind": "overflow", "reported_at": _ts(0, 17, 40),
     "updated_at": _ts(0, 18, 5), "reporter_role": "qr", "photo_path": None,
     "status": "open", "verified": 0, "report_count": 2},
    {"report_id": 2, "bin_id": "HB-1", "kind": "missed_collection", "reported_at": _ts(0, 12, 10),
     "updated_at": _ts(0, 12, 10), "reporter_role": "staff", "photo_path": None,
     "status": "in_plan", "verified": 1, "report_count": 1},
    {"report_id": 3, "bin_id": "M1-G1", "kind": "overflow", "reported_at": _ts(1, 15, 0),
     "updated_at": _ts(0, 9, 30), "reporter_role": "supervisor", "photo_path": None,
     "status": "resolved", "verified": 1, "report_count": 1},
    {"report_id": 4, "bin_id": "D1-1", "kind": "overflow", "reported_at": _ts(2, 11, 0),
     "updated_at": _ts(2, 13, 0), "reporter_role": "qr", "photo_path": None,
     "status": "rejected", "verified": 0, "report_count": 1},
]

_BATCHES = [
    {"batch_id": 1, "created_at": _ts(0, 9, 20), "updated_at": _ts(0, 9, 20),
     "source_pickup_ids": "[1]", "stream": "general", "destination": "depot",
     "status": "pending_handoff", "volume_l": 192.0},
    {"batch_id": 2, "created_at": _ts(0, 9, 40), "updated_at": _ts(0, 9, 40),
     "source_pickup_ids": "[2]", "stream": "food", "destination": "compost_stop",
     "status": "pending_handoff", "volume_l": 90.0},
    {"batch_id": 3, "created_at": _ts(1, 9, 35), "updated_at": _ts(1, 11, 0),
     "source_pickup_ids": "[3]", "stream": "food", "destination": "compost_stop",
     "status": "delivered_to_compost", "volume_l": 84.0},
]

_MEAL_KG = {"breakfast": 6, "lunch": 14, "snacks": 3, "dinner": 16}
_CATEGORY_SHARE = {"plate": 0.5, "kitchen_prep": 0.3, "unserved": 0.2}
_MESSES = ("Mess 1", "Mess 2", "Mess 3")


# ---------------------------------------------------------------- bins

def _latest(bin_id):
    """(fill_pct, observed_at ISO, stale) of a mock bin's latest reading."""
    fill, days_old = _READINGS[bin_id][:2]
    observed = datetime.combine(MOCK_SCENARIO_DATE - timedelta(days=days_old), time(20), tzinfo=TZ)
    stale = observed < MOCK_NOW - timedelta(hours=STALE_HOURS)
    return float(fill), observed.isoformat(), stale


def mock_bins() -> dict:
    rows = []
    for b in MOCK_BINS:
        fill, observed_at, stale = _latest(b["bin_id"])
        rows.append({**b, "latest_fill_pct": fill, "latest_observed_at": observed_at,
                     "latest_source": "simulated", "stale": stale})
    return {"bins": rows, "mock": True}


def mock_bin_history(bin_id: str, days: int = 14) -> dict | None:
    """None if the bin is not a mock bin."""
    if bin_id not in BINS_BY_ID:
        return None
    fill, days_old, _, inc_p50, _ = _READINGS[bin_id]
    observations, pickups = [], []
    for i in range(days):
        days_before = days - 1 - i
        if days_before < days_old:
            continue
        day = MOCK_SCENARIO_DATE - timedelta(days=days_before)
        if i > 0 and i % 4 == 0:
            pickups.append({"completed_at": f"{day}T09:00:00+05:30", "route_id": f"HIST-{day}"})
        observations.append({"observed_at": f"{day}T20:00:00+05:30",
                             "fill_pct": float(min(100, (i % 4 + 1) * inc_p50)),
                             "source": "simulated"})
    if observations:
        observations[-1]["fill_pct"] = float(fill)
    return {"bin_id": bin_id, "observations": observations, "pickups": pickups, "mock": True}


def mock_observation(bin_id: str, level=None, fill_pct=None, source="staff_tap") -> dict | None:
    """None if the bin is not a mock bin."""
    if bin_id not in BINS_BY_ID:
        return None
    value = float(LEVEL_PCT[level]) if level else float(fill_pct)
    return {"observation": {"obs_id": 9001, "bin_id": bin_id, "observed_at": now_iso(),
                            "fill_pct": value, "source": source}, "mock": True}


# ---------------------------------------------------------------- forecasts and decisions

def _p_overflow(current, p10, p50, p90):
    sigma = max((p90 - p10) / 2.563, 1.0)
    z = (OVERFLOW_PCT - (current + p50)) / sigma
    return 0.5 * math.erfc(z / math.sqrt(2))


def _forecast_rows():
    rows = []
    for i, b in enumerate(MOCK_BINS, start=1):
        current = _latest(b["bin_id"])[0]
        p10, p50, p90 = _READINGS[b["bin_id"]][2:]
        rows.append({"forecast_id": i, "bin_id": b["bin_id"], "current_fill_pct": current,
                     "predicted_increment_pct": float(p50),
                     "predicted_fill_pct": current + p50,
                     "p10_fill_pct": current + p10, "p90_fill_pct": current + p90,
                     "p_overflow": round(_p_overflow(current, p10, p50, p90), 4),
                     "horizon_end": f"{MOCK_PLAN_DATE}T23:59:59+05:30"})
    return rows


def mock_forecasts() -> dict:
    return {"plan_date": MOCK_PLAN_DATE.isoformat(), "model_version": MOCK_VERSION,
            "forecasts": _forecast_rows(), "mock": True}


def mock_forecast_eval() -> dict:
    # placeholder metric values for UI development only - not model results
    return {"model_version": MOCK_VERSION, "train_days": 35, "val_days": 10,
            "mae_model": 5.0, "mae_baseline": 6.0, "interval_coverage": 0.8,
            "n_val": 480, "mock": True}


def _reason(code, current, p, tau, report):
    if code == "overflowing_now":
        return f"Overflowing now (last reading {current:.0f}%)"
    if code == "reported":
        kind_text = "overflow" if report["kind"] == "overflow" else "missed pickup"
        return f"Reported {kind_text} by {report['reporter_role']} - {report['status']}"
    if code == "needs_review":
        return "No fresh reading in 36 h - visit and tap a level"
    if code == "p_over_tau":
        return f"{p:.0%} chance of overflow tomorrow, above tau = {tau:.2f}"
    return f"{p:.0%} chance of overflow tomorrow, below tau = {tau:.2f}"


def mock_decisions(tau: float = DEFAULT_TAU) -> dict:
    active = {r["bin_id"]: r for r in _REPORTS if r["status"] in ("open", "in_plan")}
    forecasts = {f["bin_id"]: f for f in _forecast_rows()}
    decisions = []
    for b in MOCK_BINS:
        current, _, stale = _latest(b["bin_id"])
        forecast = forecasts[b["bin_id"]]
        p = forecast["p_overflow"]
        report = active.get(b["bin_id"])
        if current >= OVERFLOW_PCT:
            code = "overflowing_now"
        elif report:
            code = "reported"
        elif stale:
            code = "needs_review"
        elif p > tau:
            code = "p_over_tau"
        else:
            code = "below_tau"
        decisions.append({
            **b, "current_fill_pct": current,
            "predicted_fill_pct": forecast["predicted_fill_pct"], "p_overflow": p,
            "selected": code != "below_tau", "reason_code": code,
            "reason": _reason(code, current, p, tau, report),
            "report_id": report["report_id"] if report else None,
            "demand_l": round(b["capacity_l"] * max(current, MIN_DEMAND_PCT) / 100, 1),
            "demand_uncertain": True})

    def count(code):
        return sum(d["reason_code"] == code for d in decisions)

    summary = {"selected": sum(d["selected"] for d in decisions),
               "skipped": count("below_tau"), "needs_review": count("needs_review"),
               "reported": count("reported"), "overflowing_now": count("overflowing_now"),
               "expected_overflows_skipped": round(sum(
                   d["p_overflow"] for d in decisions if d["reason_code"] == "below_tau"), 2)}
    return {"plan_date": MOCK_PLAN_DATE.isoformat(), "tau": tau, "decisions": decisions,
            "summary": summary, "mock": True}


# ---------------------------------------------------------------- routes

_NODES = {n["node_id"]: n for n in NODES}
_CAPACITY = {v["vehicle_id"]: v["capacity_l"] * CAPACITY_BUFFER for v in VEHICLES}


def _road_km(points):
    """Haversine km along consecutive [lat, lon] points x DETOUR_FACTOR."""
    total = 0.0
    for (lat1, lon1), (lat2, lon2) in zip(points, points[1:]):
        p1, p2 = math.radians(lat1), math.radians(lat2)
        a = (math.sin((p2 - p1) / 2) ** 2
             + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
        total += 2 * 6371.0 * math.asin(math.sqrt(a))
    return total * DETOUR_FACTOR


def _nearest_first(stops):
    """Order stops greedily by nearest neighbour, starting at the depot."""
    here = (_NODES["DEPOT"]["lat"], _NODES["DEPOT"]["lon"])
    left, ordered = list(stops), []
    while left:
        nxt = min(left, key=lambda s: _road_km([here, (s["lat"], s["lon"])]))
        ordered.append(nxt)
        left.remove(nxt)
        here = (nxt["lat"], nxt["lon"])
    return ordered


def _route(vehicle, stream, stops):
    start = _NODES["DEPOT"]
    end = _NODES["COMPOST" if stream == "food" else "DEPOT"]
    polyline = ([[start["lat"], start["lon"]]] + [[s["lat"], s["lon"]] for s in stops]
                + [[end["lat"], end["lon"]]])
    km = _road_km(polyline)
    minutes = km / SPEED_KMPH * 60 + SERVICE_MIN_PER_BIN * len(stops)
    return {"vehicle_id": vehicle["vehicle_id"], "stream": stream,
            "start_node": start["node_id"], "end_node": end["node_id"],
            "stops": [{"seq": i, "bin_id": s["bin_id"], "name": s["name"], "lat": s["lat"],
                       "lon": s["lon"], "demand_l": s["demand_l"]}
                      for i, s in enumerate(stops, start=1)],
            "ordered_bin_ids": [s["bin_id"] for s in stops],
            "km": round(km, 2), "minutes": round(minutes, 1),
            "load_l": round(sum(s["demand_l"] for s in stops), 1),
            "est_cost_rs": round(vehicle["fixed_cost_rs"] + km * vehicle["cost_per_km_rs"], 2),
            "solver": "mock", "polyline": polyline}


def _alternative(stops, fleet_size):
    """One alternative using the SPEC stream rule; stops split evenly per vehicle."""
    vehicles = VEHICLES[:fleet_size]
    general = [s for s in stops if s["stream"] == "general"]
    food = [s for s in stops if s["stream"] == "food"]
    unassigned = []
    if general and food and fleet_size == 1:
        groups = [(vehicles, "general", general)]
        unassigned = [s["bin_id"] for s in food]
    elif general and food:
        groups = [(vehicles[:-1], "general", general), (vehicles[-1:], "food", food)]
    else:
        groups = [(vehicles, "food" if food else "general", general or food)]
    routes = []
    for group_vehicles, stream, group_stops in groups:
        size = math.ceil(len(group_stops) / len(group_vehicles))
        for i, vehicle in enumerate(group_vehicles):
            chunk = group_stops[i * size:(i + 1) * size]
            if chunk:
                routes.append(_route(vehicle, stream, _nearest_first(chunk)))
    feasible = not unassigned and all(
        r["load_l"] <= _CAPACITY[r["vehicle_id"]] and r["minutes"] <= SHIFT_MIN for r in routes)
    return {"fleet_size": fleet_size, "feasible": feasible,
            "manual_dispatch_required": not feasible,
            "total_km": round(sum(r["km"] for r in routes), 2),
            "completion_minutes": max((r["minutes"] for r in routes), default=0.0),
            "total_minutes": round(sum(r["minutes"] for r in routes), 1),
            "total_cost_rs": round(sum(r["est_cost_rs"] for r in routes), 2),
            "vehicles_used": len(routes), "unassigned_bin_ids": unassigned, "routes": routes}


def mock_routes(tau: float = DEFAULT_TAU, plan_id: str | None = None) -> dict:
    """Mock POST /api/routes response. The mock baseline uses the same routes,
    so savings_vs_baseline is 0 (no invented savings)."""
    decided = mock_decisions(tau)
    stops = [d for d in decided["decisions"] if d["selected"]]
    alternatives = [_alternative(stops, k) for k in MOCK_FLEET_SIZES]
    best = min((a for a in alternatives if a["feasible"]),
               key=lambda a: (a["total_cost_rs"], a["total_km"]), default=None)
    baseline = {"method": "nearest_neighbor",
                **_alternative(stops, best["fleet_size"] if best else 2)}
    savings = None
    if best:
        km = baseline["total_km"] - best["total_km"]
        savings = {"km": round(km, 2),
                   "km_pct": round(km / baseline["total_km"] * 100, 1) if baseline["total_km"] else 0.0,
                   "cost_rs": round(baseline["total_cost_rs"] - best["total_cost_rs"], 2)}
    return {"plan_id": plan_id or f"P-{MOCK_PLAN_DATE}-{uuid.uuid4().hex[:6]}",
            "plan_date": MOCK_PLAN_DATE.isoformat(), "tau": tau,
            "decisions_summary": decided["summary"],
            "selected_bin_ids": [s["bin_id"] for s in stops],
            "alternatives": alternatives,
            "recommended_fleet_size": best["fleet_size"] if best else None,
            "baseline": baseline, "savings_vs_baseline": savings,
            "assumptions": scenario_assumptions(), "synthetic": True, "mock": True}


def mock_worker_routes() -> dict:
    plan = mock_routes(DEFAULT_TAU, plan_id=MOCK_PLAN_ID)
    alt = next((a for a in plan["alternatives"]
                if a["fleet_size"] == plan["recommended_fleet_size"]), plan["alternatives"][0])
    routes = []
    for r in alt["routes"]:
        stops = [{"seq": s["seq"], "bin_id": s["bin_id"], "name": s["name"], "lat": s["lat"],
                  "lon": s["lon"], "done": False, "completed_at": None} for s in r["stops"]]
        routes.append({"route_id": f"{MOCK_PLAN_ID}-{r['vehicle_id']}",
                       "vehicle_id": r["vehicle_id"], "stream": r["stream"],
                       "end_node": r["end_node"], "stops": stops,
                       "all_done": False, "compost_delivered": False})
    if routes:   # show one confirmed stop
        routes[0]["stops"][0].update(done=True, completed_at=f"{MOCK_PLAN_DATE}T09:20:00+05:30")
        for r in routes:
            r["all_done"] = all(s["done"] for s in r["stops"])
    return {"plan_id": MOCK_PLAN_ID, "plan_date": MOCK_PLAN_DATE.isoformat(),
            "routes": routes, "mock": True}


# ---------------------------------------------------------------- reports

def mock_reports(status: str = "open") -> dict:
    rows = [{**r, "bin_name": BINS_BY_ID[r["bin_id"]]["name"]}
            for r in _REPORTS if status == "all" or r["status"] == status]
    return {"reports": rows, "mock": True}


def mock_report_created(bin_id: str, kind: str, reporter_role: str) -> dict:
    now = now_iso()
    report = {"report_id": 101, "bin_id": bin_id, "kind": kind, "reported_at": now,
              "updated_at": now, "reporter_role": reporter_role, "photo_path": None,
              "status": "open", "verified": int(reporter_role in ("staff", "supervisor")),
              "report_count": 1}
    return {"report": report, "merged": False, "missed_collection": False, "mock": True}


def mock_report_rejected(report_id: int) -> dict:
    base = next((r for r in _REPORTS if r["report_id"] == report_id), _REPORTS[0])
    return {"report": {**base, "report_id": report_id, "status": "rejected",
                       "updated_at": now_iso()}, "mock": True}


# ---------------------------------------------------------------- pickups and batches

def mock_pickup(route_id: str, bin_id: str, level=None, staff_note=None) -> dict | None:
    """None if the bin is not a mock bin."""
    b = BINS_BY_ID.get(bin_id)
    if b is None:
        return None
    pct = LEVEL_PCT[level] if level else _latest(bin_id)[0]
    volume = round(pct * b["capacity_l"] / 100, 1)
    now = now_iso()
    pickup = {"pickup_id": 1001, "route_id": route_id, "bin_id": bin_id, "completed_at": now,
              "collected_volume_l": volume, "level": level, "staff_note": staff_note}
    batch = {"batch_id": 501, "created_at": now, "updated_at": now,
             "source_pickup_ids": "[1001]", "stream": b["stream"],
             "destination": "compost_stop" if b["stream"] == "food" else "depot",
             "status": "pending_handoff", "volume_l": volume}
    return {"pickup": pickup, "batch": batch, "mock": True}


def mock_arrive_compost(route_id: str) -> dict:
    return {"route_id": route_id, "delivered_batches": 1, "mock": True}


def mock_batches(status: str = "all") -> dict:
    rows = [b for b in _BATCHES if status == "all" or b["status"] == status]
    totals = {}
    for b in rows:
        t = totals.setdefault((b["stream"], b["status"]), {
            "stream": b["stream"], "status": b["status"], "count": 0, "volume_l": 0.0})
        t["count"] += 1
        t["volume_l"] += b["volume_l"]
    return {"batches": rows, "totals": list(totals.values()), "mock": True}


# ---------------------------------------------------------------- mess logs

def _mess_rows():
    rows, log_id = [], 0
    for days_before in range(13, -1, -1):
        day = MOCK_SCENARIO_DATE - timedelta(days=days_before)
        for m, mess_id in enumerate(_MESSES):
            for meal, kg in _MEAL_KG.items():
                for category, share in _CATEGORY_SHARE.items():
                    log_id += 1
                    rows.append({"log_id": log_id, "mess_id": mess_id, "date": day.isoformat(),
                                 "meal": meal, "category": category,
                                 "weight_kg": round(kg * share * (1 + 0.1 * m), 1),
                                 "weighed": 1, "logged_by": "simulated", "source": "simulated",
                                 "created_at": f"{day}T20:00:00+05:30"})
    rows.append({"log_id": log_id + 1, "mess_id": "Mess 1",
                 "date": MOCK_SCENARIO_DATE.isoformat(), "meal": "dinner", "category": "plate",
                 "weight_kg": 8.5, "weighed": 1, "logged_by": "mess staff", "source": "staff",
                 "created_at": _ts(0, 21, 10)})
    return rows


def mock_mess_logs(days: int = 14, mess_id: str | None = None) -> dict:
    first = (MOCK_SCENARIO_DATE - timedelta(days=days - 1)).isoformat()
    rows = [r for r in _mess_rows()
            if r["date"] >= first and (mess_id is None or r["mess_id"] == mess_id)]
    daily, meal_totals = {}, {}
    for r in rows:
        key = (r["date"], r["mess_id"])
        daily[key] = daily.get(key, 0.0) + r["weight_kg"]
        meal_key = (r["meal"], r["date"], r["mess_id"])
        meal_totals[meal_key] = meal_totals.get(meal_key, 0.0) + r["weight_kg"]
    by_meal = []
    for meal in _MEAL_KG:
        values = [v for (m, _, _), v in meal_totals.items() if m == meal]
        if values:
            by_meal.append({"meal": meal, "avg_kg": round(sum(values) / len(values), 1)})
    return {"logs": sorted(rows, key=lambda r: r["log_id"], reverse=True)[:100],
            "daily": [{"date": d, "mess_id": m, "total_kg": round(v, 1)}
                      for (d, m), v in sorted(daily.items())],
            "by_meal": by_meal,
            "synthetic_rows": sum(r["source"] == "simulated" for r in rows),
            "staff_rows": sum(r["source"] == "staff" for r in rows), "mock": True}


def mock_mess_log(body: dict) -> dict:
    log = {"log_id": 9001, "mess_id": body["mess_id"],
           "date": body.get("date") or datetime.now(TZ).date().isoformat(),
           "meal": body["meal"], "category": body["category"], "weight_kg": body["weight_kg"],
           "weighed": int(body["weighed"]), "logged_by": body.get("logged_by", "mess staff"),
           "source": "staff", "created_at": now_iso()}
    return {"log": log, "mock": True}


# ---------------------------------------------------------------- dashboard

def mock_dashboard() -> dict:
    forecasts = _forecast_rows()
    plan = mock_routes(DEFAULT_TAU, plan_id=MOCK_PLAN_ID)
    best = next((a for a in plan["alternatives"]
                 if a["fleet_size"] == plan["recommended_fleet_size"]), None)
    savings = plan["savings_vs_baseline"]
    by_day = {}
    for b in MOCK_BINS:
        for o in mock_bin_history(b["bin_id"], 14)["observations"]:
            by_day.setdefault(o["observed_at"][:10], []).append(o["fill_pct"])
    worker = mock_worker_routes()
    done = sum(s["done"] for r in worker["routes"] for s in r["stops"])
    batches = mock_batches("all")["batches"]
    mess = mock_mess_logs(7)
    reports = {s: sum(r["status"] == s for r in _REPORTS)
               for s in ("open", "in_plan", "resolved", "rejected")}
    reports["missed_collections"] = 0
    return {
        "scenario": {"scenario_date": MOCK_SCENARIO_DATE.isoformat(),
                     "plan_date": MOCK_PLAN_DATE.isoformat(), "synthetic": True},
        "fill_trend": [{"date": d, "avg_fill_pct": round(sum(v) / len(v), 1),
                        "full_bins": sum(x >= 100 for x in v)}
                       for d, v in sorted(by_day.items())],
        "forecast": {"created_at": MOCK_NOW.isoformat(),
                     "mean_p_overflow": round(sum(f["p_overflow"] for f in forecasts) / len(forecasts), 3),
                     "bins_over_half": sum(f["p_overflow"] > 0.5 for f in forecasts)},
        "plan": {"plan_id": plan["plan_id"], "plan_date": plan["plan_date"], "tau": plan["tau"],
                 "selected": plan["decisions_summary"]["selected"],
                 "skipped": plan["decisions_summary"]["skipped"],
                 "km": best["total_km"] if best else None,
                 "baseline_km": plan["baseline"]["total_km"],
                 "saving_pct": savings["km_pct"] if savings else None},
        "pickups": {"live_total": done, "today": done},
        "reports": reports,
        "batches": {
            "pending_handoff_l": sum(b["volume_l"] for b in batches if b["status"] == "pending_handoff"),
            "delivered_to_compost_l": sum(b["volume_l"] for b in batches
                                          if b["status"] == "delivered_to_compost")},
        "mess": {"last7_total_kg": round(sum(d["total_kg"] for d in mess["daily"]), 1),
                 "by_meal_avg_kg": {m["meal"]: m["avg_kg"] for m in mess["by_meal"]}},
        "mock": True}


# ---------------------------------------------------------------- twin and scale lab

def _metric_block(km, overflow_events, pickups, spread=0.05):
    """mean/min/max metrics around placeholder inputs (not twin results)."""
    def block(f):
        k = km * f
        return {"km": round(k, 1),
                "route_minutes": round(k / SPEED_KMPH * 60 + SERVICE_MIN_PER_BIN * pickups * f, 1),
                "cost_rs": round(30 * VEHICLES[0]["fixed_cost_rs"] + k * VEHICLES[0]["cost_per_km_rs"], 0),
                "overflow_events": round(overflow_events * f, 1),
                "pickups": round(pickups * f, 1)}
    return {"mean": block(1.0), "min": block(1 - spread), "max": block(1 + spread)}


def _placeholder_c(tau):
    # placeholder curve for UI development - not twin results
    return 300 * (1 - 0.5 * tau), 40 * tau, 1500 * (1 - 0.6 * tau)


def mock_twin() -> dict:
    policies = [
        {"policy": "A_fixed", "tau": None, **_metric_block(300, 0, 1500)},
        {"policy": "B_rule70", "tau": None, **_metric_block(200, 15, 800)},
        {"policy": "C_chakra", "tau": 0.5, **_metric_block(*_placeholder_c(0.5))},
    ]
    sweep = [{"tau": t, **_metric_block(*_placeholder_c(t))}
             for t in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)]
    sensitivity = []
    for detour in (1.2, 1.3, 1.5):
        for policy, (km, overflow, _) in (("A_fixed", (300, 0, 0)),
                                          ("C_chakra", _placeholder_c(0.5))):
            sensitivity.append({"detour_factor": detour, "policy": policy,
                                "km": round(km * detour / DETOUR_FACTOR, 1),
                                "overflow_events": overflow})
    return {"generated_at": MOCK_NOW.isoformat(), "synthetic": True, "days": 30,
            "seeds": [11, 22, 33], "policies": policies, "sweep": sweep,
            "sensitivity": sensitivity, "assumptions": scenario_assumptions(), "mock": True}


def mock_scale_lab() -> dict:
    def instance(name, bins, vehicles, km):
        # same placeholder km for both methods - no invented gain
        return {"name": name, "bins": bins, "vehicles": vehicles,
                "three_stage": {"km": km, "runtime_s": 0.5, "feasible": True},
                "nearest_neighbor": {"km": km, "runtime_s": 0.1, "feasible": True}}
    return {"generated_at": MOCK_NOW.isoformat(), "synthetic": True,
            "instances": [instance("campus", 50, 3, 20.0), instance("city", 1000, 20, 400.0)],
            "mock": True}
