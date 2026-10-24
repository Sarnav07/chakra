"""Health, scenario and demo reset (owner P2)."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.config import TZ_LABEL, scenario_assumptions
from app.db import get_db

router = APIRouter(tags=["core"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/scenario")
def scenario(conn: sqlite3.Connection = Depends(get_db)):
    meta = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM meta")}
    if not meta:
        raise HTTPException(404, "Database not seeded - run python -m app.seed")
    seed = meta.get("seed")
    return {
        "scenario_date": meta.get("scenario_date"),
        "plan_date": meta.get("plan_date"),
        "scenario_now": meta.get("scenario_now"),
        "timezone": TZ_LABEL,
        "synthetic": True,
        "seed": int(seed) if seed is not None else None,
        "bins_count": conn.execute("SELECT COUNT(*) FROM bins").fetchone()[0],
        "nodes": [dict(r) for r in conn.execute("SELECT * FROM nodes ORDER BY rowid")],
        "vehicles": [dict(r) for r in conn.execute("SELECT * FROM vehicles ORDER BY rowid")],
        "assumptions": scenario_assumptions(),
    }


@router.post("/demo/reset")
def demo_reset():
    try:
        from app.seed import run_seed, save_initial_forecasts
    except ImportError:
        raise HTTPException(503, "Seed not available yet - owner P1")
    summary = run_seed(seed=42)
    summary["forecasts"] = save_initial_forecasts()
    return {"ok": True, "summary": summary}
