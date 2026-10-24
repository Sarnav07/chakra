"""Dashboard summary API."""
import sqlite3

from fastapi import APIRouter, Depends

from app.dashboard.service import build_dashboard
from app.db import get_db

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(conn: sqlite3.Connection = Depends(get_db)):
    return build_dashboard(conn)
