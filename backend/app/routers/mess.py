# STUB created by P2 - owner P3 replaces the bodies
"""Mess food-waste logs (owner P3). Mock responses for now."""
from fastapi import APIRouter, Query

from app import mock_data
from app.schemas import MessLogIn

router = APIRouter(tags=["mess"])


@router.post("/mess-logs")
def create_mess_log(body: MessLogIn):
    return mock_data.mock_mess_log(body.model_dump())


@router.get("/mess-logs")
def list_mess_logs(days: int = Query(14, ge=1), mess_id: str = ""):
    return mock_data.mock_mess_logs(days, mess_id or None)
