"""Bin readings, forecasts and dispatcher decisions (P1)."""

from datetime import date, datetime, timedelta
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from app import config
from app.db import get_db, get_meta, now_iso
from app.forecast.model import evaluate, forecast_bins, persist_forecasts
from app.schemas import DecisionsIn, ObservationIn
from app.selection.select import decide

router = APIRouter(tags=["data"])


def _latest(conn):
    return {
        row["bin_id"]: row
        for row in conn.execute(
            "SELECT o.* FROM fill_observations o JOIN "
            "(SELECT bin_id, MAX(obs_id) AS obs_id FROM fill_observations GROUP BY bin_id) x "
            "ON o.obs_id=x.obs_id"
        )
    }


def _stale(observation, scenario_now):
    if observation is None:
        return True
    return datetime.fromisoformat(observation["observed_at"]) < (
        datetime.fromisoformat(scenario_now) - timedelta(hours=config.STALE_HOURS)
    )


@router.get("/bins")
def list_bins(conn: sqlite3.Connection = Depends(get_db)):
    scenario_now = get_meta(conn, "scenario_now")
    if scenario_now is None:
        raise HTTPException(404, "Database not seeded - run python -m app.seed")
    latest = _latest(conn)
    bins = []
    for row in conn.execute("SELECT * FROM bins ORDER BY bin_id"):
        observation = latest.get(row["bin_id"])
        bins.append({
            **dict(row),
            "latest_fill_pct": observation["fill_pct"] if observation else None,
            "latest_observed_at": observation["observed_at"] if observation else None,
            "latest_source": observation["source"] if observation else None,
            "stale": _stale(observation, scenario_now),
        })
    return {"bins": bins}


@router.get("/bins/{bin_id}/history")
def bin_history(bin_id: str, days: int = Query(14, ge=1), conn: sqlite3.Connection = Depends(get_db)):
    if conn.execute("SELECT 1 FROM bins WHERE bin_id=?", (bin_id,)).fetchone() is None:
        raise HTTPException(404, "Unknown bin")
    scenario_now = get_meta(conn, "scenario_now")
    end = datetime.fromisoformat(scenario_now) if scenario_now else datetime.now(config.TZ)
    start = (end - timedelta(days=days)).isoformat()
    return {
        "bin_id": bin_id,
        "observations": [dict(r) for r in conn.execute(
            "SELECT observed_at,fill_pct,source FROM fill_observations "
            "WHERE bin_id=? AND observed_at>=? ORDER BY obs_id", (bin_id, start)
        )],
        "pickups": [dict(r) for r in conn.execute(
            "SELECT completed_at,route_id FROM pickup_events "
            "WHERE bin_id=? AND completed_at>=? ORDER BY pickup_id", (bin_id, start)
        )],
    }


@router.post("/observations")
def create_observation(body: ObservationIn, conn: sqlite3.Connection = Depends(get_db)):
    bin_row = conn.execute("SELECT bin_id FROM bins WHERE bin_id=?", (body.bin_id,)).fetchone()
    if bin_row is None:
        raise HTTPException(404, "Unknown bin")
    fill = body.fill_pct if body.fill_pct is not None else config.LEVEL_PCT[body.level]
    observed_at = now_iso()
    cursor = conn.execute(
        "INSERT INTO fill_observations(bin_id,observed_at,fill_pct,source,quality) "
        "VALUES (?,?,?,?, 'ok')", (body.bin_id, observed_at, fill, body.source)
    )
    conn.commit()
    row = conn.execute("SELECT obs_id,bin_id,observed_at,fill_pct,source FROM fill_observations WHERE obs_id=?", (cursor.lastrowid,)).fetchone()
    return {"observation": dict(row)}


@router.post("/forecasts")
def run_forecasts(conn: sqlite3.Connection = Depends(get_db)):
    try:
        plan_date = date.fromisoformat(get_meta(conn, "plan_date") or "")
        forecasts = persist_forecasts(conn, forecast_bins(conn, plan_date))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return {
        "plan_date": plan_date.isoformat(),
        "model_version": forecasts[0]["model_version"] if forecasts else None,
        "forecasts": [{k: row[k] for k in (
            "forecast_id", "bin_id", "current_fill_pct", "predicted_increment_pct",
            "predicted_fill_pct", "p10_fill_pct", "p90_fill_pct", "p_overflow", "horizon_end"
        )} for row in forecasts],
    }


@router.get("/forecasts/latest")
def latest_forecasts(conn: sqlite3.Connection = Depends(get_db)):
    latest = conn.execute("SELECT MAX(created_at) FROM fill_forecasts").fetchone()[0]
    if latest is None:
        raise HTTPException(404, "No forecasts available - run POST /api/forecasts")
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM fill_forecasts WHERE created_at=? ORDER BY forecast_id", (latest,)
    )]
    return {
        "plan_date": rows[0]["plan_date"], "model_version": rows[0]["model_version"],
        "forecasts": [{k: row[k] for k in (
            "forecast_id", "bin_id", "current_fill_pct", "predicted_increment_pct",
            "predicted_fill_pct", "p10_fill_pct", "p90_fill_pct", "p_overflow", "horizon_end"
        )} for row in rows],
    }


@router.get("/forecasts/eval")
def forecast_eval(conn: sqlite3.Connection = Depends(get_db)):
    try:
        return evaluate(conn)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.post("/decisions")
def decisions(body: DecisionsIn, conn: sqlite3.Connection = Depends(get_db)):
    try:
        return decide(conn, body.tau)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
