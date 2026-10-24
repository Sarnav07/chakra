"""Read-only dashboard aggregates from the current database."""
import json
from datetime import datetime

from app import config
from app.db import get_meta


def build_dashboard(conn) -> dict:
    scenario = {"scenario_date": get_meta(conn, "scenario_date"),
                "plan_date": get_meta(conn, "plan_date"), "synthetic": True}
    trend = conn.execute(
        "SELECT substr(observed_at,1,10) AS date, AVG(fill_pct) AS avg_fill_pct,"
        "SUM(CASE WHEN fill_pct=100 THEN 1 ELSE 0 END) AS full_bins "
        "FROM fill_observations WHERE source IN ('simulated','staff_tap','camera') "
        "GROUP BY substr(observed_at,1,10) ORDER BY date DESC LIMIT 14"
    ).fetchall()
    fill_trend = [dict(row) for row in reversed(trend)]
    latest_forecast = conn.execute("SELECT MAX(created_at) FROM fill_forecasts").fetchone()[0]
    forecast = None
    if latest_forecast:
        f = conn.execute(
            "SELECT AVG(p_overflow) AS mean_p_overflow,"
            "SUM(CASE WHEN p_overflow>0.5 THEN 1 ELSE 0 END) AS bins_over_half "
            "FROM fill_forecasts WHERE created_at=?", (latest_forecast,),
        ).fetchone()
        forecast = {"created_at": latest_forecast, "mean_p_overflow": f["mean_p_overflow"],
                    "bins_over_half": f["bins_over_half"]}
    plan_row = conn.execute(
        "SELECT * FROM plans WHERE status='committed' "
        "ORDER BY created_at DESC,rowid DESC LIMIT 1"
    ).fetchone()
    plan = None
    if plan_row:
        stored = json.loads(plan_row["response_json"])
        alternative = next((a for a in stored["alternatives"]
                            if a["fleet_size"] == plan_row["chosen_fleet_size"]), None)
        baseline_km = stored["baseline"]["total_km"]
        km = alternative["total_km"] if alternative else None
        plan = {
            "plan_id": plan_row["plan_id"], "plan_date": plan_row["plan_date"],
            "tau": plan_row["tau"],
            "selected": stored["decisions_summary"]["selected"],
            "skipped": stored["decisions_summary"]["skipped"],
            "km": km, "baseline_km": baseline_km,
            "saving_pct": (round((baseline_km - km) / baseline_km * 100, 1)
                           if km is not None and baseline_km else None),
        }
    today = datetime.now(config.TZ).date().isoformat()
    p = conn.execute(
        "SELECT COUNT(*) AS live_total,"
        "SUM(CASE WHEN substr(completed_at,1,10)=? THEN 1 ELSE 0 END) AS today "
        "FROM pickup_events WHERE route_id NOT LIKE 'HIST-%'", (today,),
    ).fetchone()
    pickups = {"live_total": p["live_total"], "today": p["today"] or 0}
    reports = {status: 0 for status in ("open", "in_plan", "resolved", "rejected")}
    for row in conn.execute("SELECT status,COUNT(*) AS n FROM overflow_reports GROUP BY status"):
        reports[row["status"]] = row["n"]
    reports["missed_collections"] = conn.execute(
        "SELECT COALESCE(SUM(missed),0) FROM pickup_decisions"
    ).fetchone()[0]
    b = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN status='pending_handoff' THEN volume_l END),0) AS pending,"
        "COALESCE(SUM(CASE WHEN status='delivered_to_compost' THEN volume_l END),0) AS delivered "
        "FROM batch_events"
    ).fetchone()
    batches = {"pending_handoff_l": b["pending"],
               "delivered_to_compost_l": b["delivered"]}
    meal_dates = [r[0] for r in conn.execute(
        "SELECT DISTINCT date FROM mess_waste_logs ORDER BY date DESC LIMIT 7"
    )]
    mess_total = 0.0
    meal_avg = {}
    if meal_dates:
        marks = ",".join("?" for _ in meal_dates)
        mess_total = conn.execute(
            f"SELECT COALESCE(SUM(weight_kg),0) FROM mess_waste_logs WHERE date IN ({marks})",
            meal_dates,
        ).fetchone()[0]
        meal_avg = {row["meal"]: row["avg_kg"] for row in conn.execute(
            f"SELECT meal,AVG(weight_kg) AS avg_kg FROM mess_waste_logs "
            f"WHERE date IN ({marks}) GROUP BY meal", meal_dates,
        )}
    return {
        "scenario": scenario, "fill_trend": fill_trend, "forecast": forecast,
        "plan": plan, "pickups": pickups, "reports": reports, "batches": batches,
        "mess": {"last7_total_kg": mess_total, "by_meal_avg_kg": meal_avg},
    }
