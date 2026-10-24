"""Dashboard summary (SPEC Section 14, GET /api/dashboard).

build_dashboard(conn) returns the complete dashboard payload:
  scenario, fill_trend, forecast, plan, pickups, reports, batches, mess.

mess.last7_total_kg = total weight_kg over the last 7 dates that have
mess logs (1 dp).
mess.by_meal_avg_kg = {breakfast, lunch, snacks, dinner}: for each meal,
the average over those 7 dates of that date's total kg for the meal
(across all messes), rounded to 1 dp.
"""

import json
from datetime import datetime

from app import config
from app.db import get_meta


def build_dashboard(conn) -> dict:
    scenario_date = get_meta(conn, "scenario_date")
    plan_date = get_meta(conn, "plan_date")
    scenario = {
        "scenario_date": scenario_date,
        "plan_date": plan_date,
        "synthetic": True,
    }

    fill_trend = _fill_trend(conn)
    forecast = _forecast(conn)
    plan = _plan(conn)
    pickups = _pickups(conn)
    reports = _reports(conn)
    batches = _batches(conn)
    mess = _mess(conn)

    return {
        "scenario": scenario,
        "fill_trend": fill_trend,
        "forecast": forecast,
        "plan": plan,
        "pickups": pickups,
        "reports": reports,
        "batches": batches,
        "mess": mess,
    }


def _fill_trend(conn) -> list:
    rows = conn.execute(
        "SELECT substr(observed_at,1,10) AS date, "
        "ROUND(AVG(fill_pct), 1) AS avg_fill_pct, "
        "SUM(CASE WHEN fill_pct >= 100 THEN 1 ELSE 0 END) AS full_bins "
        "FROM fill_observations "
        "WHERE source IN ('simulated','staff_tap','camera') "
        "GROUP BY substr(observed_at,1,10) "
        "ORDER BY date DESC LIMIT 14"
    ).fetchall()
    return [dict(r) for r in reversed(rows)]


def _forecast(conn) -> dict | None:
    row = conn.execute(
        "SELECT MAX(created_at) AS ca FROM fill_forecasts"
    ).fetchone()
    if row is None or row["ca"] is None:
        return None

    newest = row["ca"]
    f = conn.execute(
        "SELECT ROUND(AVG(p_overflow), 3) AS mean_p_overflow, "
        "SUM(CASE WHEN p_overflow > 0.5 THEN 1 ELSE 0 END) AS bins_over_half "
        "FROM fill_forecasts WHERE created_at = ? AND p_overflow IS NOT NULL",
        (newest,),
    ).fetchone()

    if f["mean_p_overflow"] is None:
        return {"created_at": newest, "mean_p_overflow": None, "bins_over_half": 0}

    return {
        "created_at": newest,
        "mean_p_overflow": float(f["mean_p_overflow"]),
        "bins_over_half": int(f["bins_over_half"]),
    }


def _plan(conn) -> dict | None:
    row = conn.execute(
        "SELECT * FROM plans WHERE status = 'committed' "
        "ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None

    try:
        resp = json.loads(row["response_json"])
    except (json.JSONDecodeError, TypeError):
        resp = {}

    ds = resp.get("decisions_summary") or {}
    selected = ds.get("selected")
    skipped = ds.get("skipped")

    chosen_fleet = row["chosen_fleet_size"]
    km = None
    for alt in (resp.get("alternatives") or []):
        if alt.get("fleet_size") == chosen_fleet:
            km = alt.get("total_km")
            break

    baseline = resp.get("baseline") or {}
    baseline_km = baseline.get("total_km")

    saving_pct = None
    if baseline_km and km is not None:
        saving_pct = round((baseline_km - km) / baseline_km * 100, 1)

    return {
        "plan_id": row["plan_id"],
        "plan_date": row["plan_date"],
        "tau": row["tau"],
        "selected": selected,
        "skipped": skipped,
        "km": km,
        "baseline_km": baseline_km,
        "saving_pct": saving_pct,
    }


def _pickups(conn) -> dict:
    today = datetime.now(config.TZ).date().isoformat()
    p = conn.execute(
        "SELECT COUNT(*) AS live_total, "
        "SUM(CASE WHEN substr(completed_at,1,10) = ? THEN 1 ELSE 0 END) AS today "
        "FROM pickup_events WHERE route_id NOT LIKE 'HIST-%'",
        (today,),
    ).fetchone()
    return {"live_total": p["live_total"], "today": p["today"] or 0}


def _reports(conn) -> dict:
    counts = {s: 0 for s in ("open", "in_plan", "resolved", "rejected")}
    for r in conn.execute(
        "SELECT status, COUNT(*) AS n FROM overflow_reports GROUP BY status"
    ).fetchall():
        counts[r["status"]] = r["n"]

    missed = conn.execute(
        "SELECT COALESCE(SUM(missed), 0) FROM pickup_decisions"
    ).fetchone()[0]

    counts["missed_collections"] = int(missed)
    return counts


def _batches(conn) -> dict:
    b = conn.execute(
        "SELECT "
        "COALESCE(SUM(CASE WHEN status='pending_handoff' THEN volume_l END), 0) AS pending, "
        "COALESCE(SUM(CASE WHEN status='delivered_to_compost' THEN volume_l END), 0) AS delivered "
        "FROM batch_events"
    ).fetchone()
    return {
        "pending_handoff_l": round(float(b["pending"]), 1),
        "delivered_to_compost_l": round(float(b["delivered"]), 1),
    }


def _mess(conn) -> dict:
    date_rows = conn.execute(
        "SELECT DISTINCT date FROM mess_waste_logs ORDER BY date DESC LIMIT 7"
    ).fetchall()
    last7_dates = [r["date"] for r in date_rows]

    if not last7_dates:
        return {
            "last7_total_kg": 0.0,
            "by_meal_avg_kg": {
                "breakfast": 0.0,
                "lunch": 0.0,
                "snacks": 0.0,
                "dinner": 0.0,
            },
        }

    marks = ",".join("?" for _ in last7_dates)
    n_dates = len(last7_dates)

    total = conn.execute(
        f"SELECT COALESCE(SUM(weight_kg), 0) AS t "
        f"FROM mess_waste_logs WHERE date IN ({marks})",
        last7_dates,
    ).fetchone()
    last7_total_kg = round(float(total["t"]), 1)

    meal_rows = conn.execute(
        f"SELECT meal, date, SUM(weight_kg) AS day_total "
        f"FROM mess_waste_logs WHERE date IN ({marks}) "
        f"GROUP BY meal, date",
        last7_dates,
    ).fetchall()

    meal_date_totals: dict[str, list[float]] = {}
    for r in meal_rows:
        meal_date_totals.setdefault(r["meal"], []).append(float(r["day_total"]))

    by_meal_avg_kg = {}
    for meal in ("breakfast", "lunch", "snacks", "dinner"):
        vals = meal_date_totals.get(meal, [])
        by_meal_avg_kg[meal] = round(sum(vals) / n_dates, 1) if vals else 0.0

    return {
        "last7_total_kg": last7_total_kg,
        "by_meal_avg_kg": by_meal_avg_kg,
    }
