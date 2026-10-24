"""Pickups, compost arrival and batches (owner P3)."""
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db
from app.pickups.service import (
    BadRequest,
    Conflict,
    NotFound,
    arrive_compost,
    confirm_pickup,
    list_batches,
)
from app.schemas import CompostIn, PickupIn

router = APIRouter(tags=["pickups"])


@router.post("/pickups")
def do_confirm_pickup(body: PickupIn, conn: sqlite3.Connection = Depends(get_db)):
    try:
        return confirm_pickup(conn, body.route_id, body.bin_id, body.level, body.staff_note)
    except NotFound as exc:
        raise HTTPException(404, str(exc)) from None
    except BadRequest as exc:
        raise HTTPException(400, str(exc)) from None
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from None


@router.post("/pickups/arrive-compost")
def do_arrive_compost(body: CompostIn, conn: sqlite3.Connection = Depends(get_db)):
    try:
        return arrive_compost(conn, body.route_id)
    except NotFound as exc:
        raise HTTPException(404, str(exc)) from None
    except BadRequest as exc:
        raise HTTPException(400, str(exc)) from None
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from None


@router.get("/batches")
def do_list_batches(
    status: Literal["pending_handoff", "delivered_to_compost", "all"] = "all",
    conn: sqlite3.Connection = Depends(get_db),
):
    return list_batches(conn, status)
