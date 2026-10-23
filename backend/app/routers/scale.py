"""Scale lab endpoints (owner P2)."""
import json

from fastapi import APIRouter, HTTPException

from app.config import DEMO_CACHE_DIR

router = APIRouter(tags=["scale"])

SCALE_CACHE = DEMO_CACHE_DIR / "scale_lab.json"


@router.get("/scale-lab")
def get_scale_lab():
    if not SCALE_CACHE.exists():
        raise HTTPException(404, "Scale lab not cached - run POST /api/scale-lab/run")
    return json.loads(SCALE_CACHE.read_text(encoding="utf-8"))


@router.post("/scale-lab/run")
def run_scale_lab():
    raise HTTPException(501, "Not built yet")
