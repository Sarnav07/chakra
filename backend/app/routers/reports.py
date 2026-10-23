"""Overflow / missed-collection reports (owner P2)."""
import sqlite3
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.config import DATA_DIR, MAX_UPLOAD_MB, UPLOAD_DIR
from app.db import get_db
from app.reports.service import ReportConflict, create_report, list_reports, reject_report

router = APIRouter(tags=["reports"])

# content type -> (file extension, required leading bytes)
PHOTO_TYPES = {"image/jpeg": (".jpg", b"\xff\xd8\xff"),
               "image/png": (".png", b"\x89PNG\r\n\x1a\n")}


def _save_photo(photo: UploadFile) -> str:
    """Check type and size, save under UPLOAD_DIR/reports, return the path
    relative to DATA_DIR. Raises HTTP 400 for a bad file."""
    if photo.content_type not in PHOTO_TYPES:
        raise HTTPException(400, "Photo must be a JPEG or PNG image")
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    data = photo.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(400, f"Photo is larger than {MAX_UPLOAD_MB} MB")
    extension, magic = PHOTO_TYPES[photo.content_type]
    if not data.startswith(magic):
        raise HTTPException(400, "Photo must be a JPEG or PNG image")
    folder = UPLOAD_DIR / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}{extension}"
    path.write_bytes(data)
    return path.relative_to(DATA_DIR).as_posix()


@router.post("/reports")
def post_report(bin_id: str = Form(...),
                kind: Literal["overflow", "missed_collection"] = Form(...),
                reporter_role: Literal["staff", "qr", "supervisor"] = Form(...),
                photo: UploadFile | None = File(None),
                conn: sqlite3.Connection = Depends(get_db)):
    if conn.execute("SELECT 1 FROM bins WHERE bin_id = ?", (bin_id,)).fetchone() is None:
        raise HTTPException(404, "Unknown bin")
    photo_path = _save_photo(photo) if photo is not None and photo.filename else None
    return create_report(conn, bin_id, kind, reporter_role, photo_path)


@router.get("/reports")
def get_reports(status: Literal["open", "in_plan", "resolved", "rejected", "all"] = "open",
                conn: sqlite3.Connection = Depends(get_db)):
    return list_reports(conn, status)


@router.post("/reports/{report_id}/reject")
def post_reject(report_id: int, conn: sqlite3.Connection = Depends(get_db)):
    try:
        return {"report": reject_report(conn, report_id)}
    except LookupError:
        raise HTTPException(404, "Report not found")
    except ReportConflict as exc:
        raise HTTPException(409, str(exc))
