"""Overflow / missed-collection reports (owner P2). Mock responses for now."""
from typing import Literal

from fastapi import APIRouter, File, Form, UploadFile

from app import mock_data

router = APIRouter(tags=["reports"])


@router.post("/reports")
def create_report(bin_id: str = Form(...),
                  kind: Literal["overflow", "missed_collection"] = Form(...),
                  reporter_role: Literal["staff", "qr", "supervisor"] = Form(...),
                  photo: UploadFile | None = File(None)):
    return mock_data.mock_report_created(bin_id, kind, reporter_role)


@router.get("/reports")
def list_reports(status: Literal["open", "in_plan", "resolved", "rejected", "all"] = "open"):
    return mock_data.mock_reports(status)


@router.post("/reports/{report_id}/reject")
def reject_report(report_id: int):
    return mock_data.mock_report_rejected(report_id)
