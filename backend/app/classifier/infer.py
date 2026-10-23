# STUB created by P2 - owner P1 replaces this file
"""Item classifier inference (SPEC Section 13). Stub: the model is never available."""

CLASSES = ["battery", "metal", "organic", "other", "paper", "plastic"]


class ClassifierUnavailable(Exception):
    """torch is not installed or the model file is missing."""


def classifier_status() -> dict:
    return {"available": False, "model_version": None, "classes": list(CLASSES),
            "report": None}


def classify_image(image_bytes: bytes) -> dict:
    raise ClassifierUnavailable("Classifier model not available")
