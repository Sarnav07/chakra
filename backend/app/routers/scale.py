"""Scale lab endpoints (owner P2)."""
from fastapi import APIRouter, HTTPException

from app.scale_lab.run import load_scale_cache, run_scale_lab

router = APIRouter(tags=["scale"])


@router.get("/scale-lab")
def get_scale_lab():
    cached = load_scale_cache()
    if cached is None:
        raise HTTPException(404, "Scale lab not cached - run POST /api/scale-lab/run")
    return cached


@router.post("/scale-lab/run")
def post_scale_lab_run():
    return run_scale_lab()
