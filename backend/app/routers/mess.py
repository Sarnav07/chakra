"""Mess food-waste logs (owner P3)."""
import sqlite3

from fastapi import APIRouter, Depends, Query

from app.db import get_db
from app.mess.service import MessValidationError, create_log, list_logs
from app.schemas import MessLogIn

router = APIRouter(tags=["mess"])


@router.post("/mess-logs")
def do_create_mess_log(body: MessLogIn, conn: sqlite3.Connection = Depends(get_db)):
    try:
        return create_log(conn, body.model_dump())
    except MessValidationError as exc:
        from fastapi import HTTPException
        raise HTTPException(422, str(exc)) from None


@router.get("/mess-logs")
def do_list_mess_logs(
    days: int = Query(14, ge=1),
    mess_id: str = "",
    conn: sqlite3.Connection = Depends(get_db),
):
    return list_logs(conn, days, mess_id or None)
