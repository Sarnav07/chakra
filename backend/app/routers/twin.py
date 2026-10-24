"""Cached synthetic policy comparison."""

from fastapi import APIRouter, HTTPException

from app.twin.policies import load_twin_cache, run_twin

router = APIRouter(tags=["twin"])


@router.get("/twin")
def get_twin():
    result = load_twin_cache()
    if result is None:
        raise HTTPException(404, "Twin results not cached - run POST /api/twin/run")
    return result


@router.post("/twin/run")
def run_twin_endpoint():
    return run_twin()
