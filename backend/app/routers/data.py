# STUB created by P2 - owner P1 replaces the bodies
"""Bins, observations, forecasts and decisions (owner P1). Mock responses for now."""
from fastapi import APIRouter, HTTPException, Query

from app import mock_data
from app.schemas import DecisionsIn, ObservationIn

router = APIRouter(tags=["data"])


@router.get("/bins")
def list_bins():
    return mock_data.mock_bins()


@router.get("/bins/{bin_id}/history")
def bin_history(bin_id: str, days: int = Query(14, ge=1)):
    history = mock_data.mock_bin_history(bin_id, days)
    if history is None:
        raise HTTPException(404, "Unknown bin")
    return history


@router.post("/observations")
def create_observation(body: ObservationIn):
    result = mock_data.mock_observation(body.bin_id, body.level, body.fill_pct, body.source)
    if result is None:
        raise HTTPException(404, "Unknown bin")
    return result


@router.post("/forecasts")
def run_forecasts():
    return mock_data.mock_forecasts()


@router.get("/forecasts/latest")
def latest_forecasts():
    return mock_data.mock_forecasts()


@router.get("/forecasts/eval")
def forecast_eval():
    return mock_data.mock_forecast_eval()


@router.post("/decisions")
def decisions(body: DecisionsIn):
    return mock_data.mock_decisions(body.tau)
