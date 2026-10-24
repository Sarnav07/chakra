"""Mess food-waste logs (SPEC Sections 7, 11, 14)."""

from datetime import datetime

from app import config
from app.db import now_iso

VALID_MEALS = ("breakfast", "lunch", "snacks", "dinner")
VALID_CATEGORIES = ("plate", "kitchen_prep", "unserved")


class MessValidationError(Exception):
    pass


def create_log(conn, body: dict) -> dict:
    """Insert a mess waste log entry. Returns {"log": row}."""
    mess_id = body.get("mess_id", "")
    exists = conn.execute(
        "SELECT 1 FROM bins WHERE group_name = ? AND group_type IN ('mess', 'mess_food') LIMIT 1",
        (mess_id,),
    ).fetchone()
    if exists is None:
        raise MessValidationError(f"Unknown mess: {mess_id}")

    meal = body.get("meal", "")
    if meal not in VALID_MEALS:
        raise MessValidationError(f"Invalid meal: {meal}")

    category = body.get("category", "")
    if category not in VALID_CATEGORIES:
        raise MessValidationError(f"Invalid category: {category}")

    weight_kg = body.get("weight_kg")
    if weight_kg is None or not (0 < weight_kg <= 500):
        raise MessValidationError("weight_kg must be between 0 (exclusive) and 500")

    weighed_raw = body.get("weighed", False)
    weighed = 1 if weighed_raw else 0

    log_date = body.get("date")
    if not log_date:
        log_date = datetime.now(config.TZ).date().isoformat()

    logged_by = body.get("logged_by") or "staff"
    created_at = now_iso()

    cursor = conn.execute(
        "INSERT INTO mess_waste_logs "
        "(mess_id, date, meal, category, weight_kg, weighed, logged_by, source, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'staff', ?)",
        (mess_id, log_date, meal, category, round(weight_kg, 1), weighed, logged_by, created_at),
    )
    conn.commit()
    row = dict(conn.execute(
        "SELECT * FROM mess_waste_logs WHERE log_id = ?", (cursor.lastrowid,)
    ).fetchone())
    return {"log": row}


def list_logs(conn, days: int = 14, mess_id: str | None = None) -> dict:
    """Return latest logs, daily totals, by-meal averages and source counts.

    avg_kg = average over dates of each date's total kg for that meal.
    """
    mess_filter = ""
    params = []
    if mess_id:
        mess_filter = " AND mess_id = ?"
        params = [mess_id]

    rows = conn.execute(
        f"SELECT * FROM mess_waste_logs WHERE 1=1 {mess_filter} "
        "ORDER BY log_id DESC LIMIT 100",
        params,
    ).fetchall()
    logs = [dict(r) for r in rows]

    daily_rows = conn.execute(
        f"SELECT date, mess_id, ROUND(SUM(weight_kg), 1) AS total_kg "
        f"FROM mess_waste_logs WHERE 1=1 {mess_filter} "
        "GROUP BY date, mess_id ORDER BY date DESC",
        params,
    ).fetchall()

    dates_seen = set()
    daily = []
    for r in daily_rows:
        dates_seen.add(r["date"])
        if len(dates_seen) <= days:
            daily.append({"date": r["date"], "mess_id": r["mess_id"],
                          "total_kg": float(r["total_kg"])})

    date_limit = sorted(dates_seen, reverse=True)[:days]

    if date_limit:
        placeholders = ",".join("?" * len(date_limit))
        meal_query_params = list(date_limit) + params
        meal_rows = conn.execute(
            f"SELECT meal, date, SUM(weight_kg) AS day_total "
            f"FROM mess_waste_logs WHERE date IN ({placeholders}) {mess_filter} "
            "GROUP BY meal, date",
            meal_query_params,
        ).fetchall()

        meal_date_totals = {}
        for r in meal_rows:
            key = r["meal"]
            if key not in meal_date_totals:
                meal_date_totals[key] = []
            meal_date_totals[key].append(float(r["day_total"]))

        by_meal = [
            {"meal": meal, "avg_kg": round(sum(vals) / len(vals), 1)}
            for meal, vals in sorted(meal_date_totals.items())
        ]
    else:
        by_meal = []

    count_params = params
    counts = conn.execute(
        f"SELECT source, COUNT(*) AS cnt FROM mess_waste_logs "
        f"WHERE 1=1 {mess_filter} GROUP BY source",
        count_params,
    ).fetchall()
    counts_map = {r["source"]: r["cnt"] for r in counts}

    return {
        "logs": logs,
        "daily": daily,
        "by_meal": by_meal,
        "synthetic_rows": counts_map.get("simulated", 0),
        "staff_rows": counts_map.get("staff", 0),
    }
