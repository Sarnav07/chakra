"""Pickup confirmation, compost arrival and batches (SPEC Sections 11, 14, 15)."""

import json

from app import config
from app.db import now_iso


class NotFound(Exception):
    pass


class BadRequest(Exception):
    pass


class Conflict(Exception):
    pass


def confirm_pickup(conn, route_id, bin_id, level=None, staff_note=None) -> dict:
    """Confirm a pickup and create the associated batch and reset observation."""
    route = conn.execute(
        "SELECT * FROM route_plans WHERE route_id = ?", (route_id,)
    ).fetchone()
    if route is None:
        raise NotFound(f"Route {route_id} not found")

    ordered = json.loads(route["ordered_bin_ids"])
    if bin_id not in ordered:
        raise BadRequest(f"Bin {bin_id} is not on route {route_id}")

    if level is not None and level not in config.LEVEL_PCT:
        raise BadRequest(f"Invalid level: {level}")

    existing = conn.execute(
        "SELECT 1 FROM pickup_events WHERE route_id = ? AND bin_id = ?",
        (route_id, bin_id),
    ).fetchone()
    if existing is not None:
        raise Conflict("Pickup already confirmed")

    bin_row = conn.execute(
        "SELECT * FROM bins WHERE bin_id = ?", (bin_id,)
    ).fetchone()
    capacity = float(bin_row["capacity_l"])

    if level is not None:
        collected_volume_l = config.LEVEL_PCT[level] * capacity / 100.0
    else:
        latest_obs = conn.execute(
            "SELECT fill_pct FROM fill_observations "
            "WHERE bin_id = ? ORDER BY obs_id DESC LIMIT 1",
            (bin_id,),
        ).fetchone()
        if latest_obs is not None:
            collected_volume_l = float(latest_obs["fill_pct"]) * capacity / 100.0
        else:
            collected_volume_l = 0.0

    now = now_iso()
    try:
        cursor = conn.execute(
            "INSERT INTO pickup_events "
            "(route_id, bin_id, completed_at, collected_volume_l, level, staff_note) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (route_id, bin_id, now, collected_volume_l, level, staff_note),
        )
        pickup_id = cursor.lastrowid

        conn.execute(
            "INSERT INTO fill_observations "
            "(bin_id, observed_at, fill_pct, source, quality) "
            "VALUES (?, ?, 0, 'pickup_reset', 'ok')",
            (bin_id, now),
        )

        stream = bin_row["stream"]
        destination = "compost_stop" if stream == "food" else "depot"
        conn.execute(
            "INSERT INTO batch_events "
            "(created_at, updated_at, source_pickup_ids, stream, destination, status, volume_l) "
            "VALUES (?, ?, ?, ?, ?, 'pending_handoff', ?)",
            (now, now, json.dumps([pickup_id]), stream, destination, collected_volume_l),
        )
        batch_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        from app.reports.service import mark_resolved
        mark_resolved(conn, bin_id)

        pickup_row = dict(conn.execute(
            "SELECT * FROM pickup_events WHERE pickup_id = ?", (pickup_id,)
        ).fetchone())
        batch_row = dict(conn.execute(
            "SELECT * FROM batch_events WHERE batch_id = ?", (batch_id,)
        ).fetchone())

        return {"pickup": pickup_row, "batch": batch_row}
    except Exception:
        conn.rollback()
        raise


def arrive_compost(conn, route_id) -> dict:
    """Mark food batches as delivered to compost stop."""
    route = conn.execute(
        "SELECT * FROM route_plans WHERE route_id = ?", (route_id,)
    ).fetchone()
    if route is None:
        raise NotFound(f"Route {route_id} not found")

    if route["stream"] != "food":
        raise BadRequest("Only food routes can arrive at the compost stop")

    ordered = json.loads(route["ordered_bin_ids"])
    for bin_id in ordered:
        pickup = conn.execute(
            "SELECT 1 FROM pickup_events WHERE route_id = ? AND bin_id = ?",
            (route_id, bin_id),
        ).fetchone()
        if pickup is None:
            raise Conflict(
                f"Not all stops confirmed yet (missing {bin_id})"
            )

    now = now_iso()
    pickup_ids = [
        row["pickup_id"]
        for row in conn.execute(
            "SELECT pickup_id FROM pickup_events WHERE route_id = ?", (route_id,)
        ).fetchall()
    ]

    count = 0
    for row in conn.execute(
        "SELECT batch_id, source_pickup_ids FROM batch_events "
        "WHERE status = 'pending_handoff'"
    ).fetchall():
        batch_pickup_ids = json.loads(row["source_pickup_ids"])
        if any(pid in pickup_ids for pid in batch_pickup_ids):
            conn.execute(
                "UPDATE batch_events SET status = 'delivered_to_compost', updated_at = ? "
                "WHERE batch_id = ?",
                (now, row["batch_id"]),
            )
            count += 1
    conn.commit()
    return {"route_id": route_id, "delivered_batches": count}


def list_batches(conn, status="all") -> dict:
    """Return batches and summary totals."""
    if status == "all":
        rows = conn.execute(
            "SELECT * FROM batch_events ORDER BY batch_id DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM batch_events WHERE status = ? ORDER BY batch_id DESC",
            (status,),
        ).fetchall()

    batches = [dict(r) for r in rows]

    totals_map = {}
    for b in batches:
        key = (b["stream"], b["status"])
        if key not in totals_map:
            totals_map[key] = {"stream": b["stream"], "status": b["status"],
                               "count": 0, "volume_l": 0.0}
        totals_map[key]["count"] += 1
        totals_map[key]["volume_l"] = round(totals_map[key]["volume_l"] + b["volume_l"], 2)

    return {"batches": batches, "totals": list(totals_map.values())}
