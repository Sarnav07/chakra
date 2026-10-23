# STUB created by P2 - owner P1 replaces the bodies
"""Digital twin results (owner P1). Mock responses for now."""
from fastapi import APIRouter

from app import mock_data

router = APIRouter(tags=["twin"])


@router.get("/twin")
def get_twin():
    return mock_data.mock_twin()


@router.post("/twin/run")
def run_twin():
    return mock_data.mock_twin()
