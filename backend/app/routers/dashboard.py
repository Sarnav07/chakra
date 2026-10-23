# STUB created by P2 - owner P3 replaces the bodies
"""Dashboard summary (owner P3). Mock response for now."""
from fastapi import APIRouter

from app import mock_data

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard():
    return mock_data.mock_dashboard()
