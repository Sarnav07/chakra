# STUB created by P2 - owner P3 replaces the bodies
"""Pickups, compost arrival and batches (owner P3). Mock responses for now."""
from typing import Literal

from fastapi import APIRouter, HTTPException

from app import mock_data
from app.schemas import CompostIn, PickupIn

router = APIRouter(tags=["pickups"])


@router.post("/pickups")
def confirm_pickup(body: PickupIn):
    result = mock_data.mock_pickup(body.route_id, body.bin_id, body.level, body.staff_note)
    if result is None:
        raise HTTPException(400, "Bin is not on this route")
    return result


@router.post("/pickups/arrive-compost")
def arrive_compost(body: CompostIn):
    return mock_data.mock_arrive_compost(body.route_id)


@router.get("/batches")
def list_batches(status: Literal["pending_handoff", "delivered_to_compost", "all"] = "all"):
    return mock_data.mock_batches(status)
