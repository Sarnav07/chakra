# STUB created by P2 - owner P1 replaces the bodies
"""Item classifier endpoints (owner P1). The stub model is never available."""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.classifier.infer import classifier_status

router = APIRouter(tags=["classify"])


@router.get("/classify/status")
def classify_status():
    return classifier_status()


@router.post("/classify")
def classify(photo: UploadFile | None = File(None), bin_id: str | None = Form(None)):
    raise HTTPException(503, "Classifier model not available")
