# STUB created by P2 - owner P1 replaces the bodies
"""Single-item photo classifier API (P1)."""

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app import config
from app.classifier.infer import ClassifierUnavailable, classifier_status, classify_image
from app.db import get_db, now_iso

router = APIRouter(tags=["classify"])


@router.get("/classify/status")
def classify_status():
    return classifier_status()


@router.post("/classify")
def classify(
    photo: UploadFile | None = File(None), bin_id: str | None = Form(None), conn=Depends(get_db)
):
    if photo is None:
        raise HTTPException(400, "Upload one JPEG or PNG photo")
    suffix_by_type = {"image/jpeg": ".jpg", "image/png": ".png"}
    if photo.content_type not in suffix_by_type:
        raise HTTPException(400, "Only JPEG and PNG photos are supported")
    contents = photo.file.read(config.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if not contents or len(contents) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(400, f"Photo must be no larger than {config.MAX_UPLOAD_MB} MB")
    try:
        with Image.open(BytesIO(contents)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(400, "Invalid image file") from None

    try:
        result = classify_image(contents)
    except ClassifierUnavailable:
        raise HTTPException(503, "Classifier model not available") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None

    model_version = classifier_status()["model_version"]
    checked_at = now_iso()
    directory = Path(config.UPLOAD_DIR) / "checks"
    directory.mkdir(parents=True, exist_ok=True)
    image_path = directory / f"{uuid4().hex}{suffix_by_type[photo.content_type]}"
    image_path.write_bytes(contents)
    cursor = conn.execute(
        "INSERT INTO item_checks(image_path,predicted_class,confidence,hazardous,unsure,"
        "suggested_bin,model_version,checked_at,bin_id) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            str(image_path), result["predicted_class"], result["confidence"],
            int(result["hazardous"]), int(result["unsure"]), result["suggested_bin"],
            model_version, checked_at, bin_id,
        ),
    )
    conn.commit()
    return {"check_id": cursor.lastrowid, **result, "model_version": model_version, "checked_at": checked_at}
