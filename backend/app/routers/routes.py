"""Route plans, plan choice and worker routes (owner P2). Mock responses for now."""
from fastapi import APIRouter, HTTPException

from app import mock_data
from app.config import DEFAULT_TAU
from app.schemas import ChooseIn, RoutesIn

router = APIRouter(tags=["routes"])


@router.post("/routes")
def create_routes(body: RoutesIn):
    return mock_data.mock_routes(body.tau)


@router.get("/routes/{plan_id}")
def get_plan(plan_id: str):
    return mock_data.mock_routes(DEFAULT_TAU, plan_id=plan_id)


@router.post("/routes/{plan_id}/choose")
def choose_plan(plan_id: str, body: ChooseIn):
    plan = mock_data.mock_routes(DEFAULT_TAU, plan_id=plan_id)
    alt = next((a for a in plan["alternatives"] if a["fleet_size"] == body.fleet_size), None)
    if alt is None:
        raise HTTPException(404, f"No alternative with fleet_size {body.fleet_size} in this plan")
    if not alt["feasible"]:
        raise HTTPException(409, "This alternative is infeasible - manual dispatch required")
    return {"plan_id": plan_id, "status": "committed",
            "route_ids": [f"{plan_id}-{r['vehicle_id']}" for r in alt["routes"]], "mock": True}


@router.get("/worker/routes")
def worker_routes():
    return mock_data.mock_worker_routes()
