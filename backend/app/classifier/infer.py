"""CPU inference for one waste item photo.

The six internal model outputs route to five ordinary bins plus a separate
battery safety warning. Image checks are advisory, never automatic actuation.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path


CLASSES = ("battery", "metal", "organic", "other", "paper", "plastic")
SUGGESTED_BIN = {
    "paper": "Dry waste - paper",
    "plastic": "Dry waste - plastic",
    "metal": "Dry waste - metal",
    "organic": "Wet waste - food and organic",
    "other": "Other / reject",
    "battery": "Hazardous - hand over for special pickup",
}
CONFIDENCE_THRESHOLD = 0.6
_cached_model = None
_cached_checkpoint = None
_cached_path = None
_cached_mtime_ns = None


class ClassifierUnavailable(RuntimeError):
    pass


def _model_dir(model_dir: Path | None = None) -> Path:
    if model_dir is not None:
        return Path(model_dir)
    try:
        from app.config import MODEL_DIR
    except (ImportError, AttributeError):
        return Path(os.environ.get("CHAKRA_MODEL_DIR", "backend/data/model"))
    return Path(MODEL_DIR)


def build_result(probs: list[float], classes: list[str], threshold: float = CONFIDENCE_THRESHOLD) -> dict:
    if classes != list(CLASSES) or len(probs) != len(CLASSES):
        raise ValueError("Probabilities must use the six-class CHAKRA checkpoint order")
    if not all(isinstance(value, (int, float)) and 0 <= value <= 1 for value in probs):
        raise ValueError("Probabilities must be finite values between 0 and 1")
    if abs(sum(probs) - 1.0) > 1e-3:
        raise ValueError("Probabilities must sum to 1")
    if not 0 < threshold < 1:
        raise ValueError("Confidence threshold must lie strictly between 0 and 1")
    order = sorted(range(len(probs)), key=lambda index: probs[index], reverse=True)
    top = order[0]
    predicted = classes[top]
    confidence = float(probs[top])
    hazardous = predicted == "battery"
    unsure = confidence < threshold
    return {
        "predicted_class": predicted,
        "confidence": confidence,
        "top3": [{"class": classes[index], "confidence": float(probs[index])} for index in order[:3]],
        "unsure": unsure,
        "hazardous": hazardous,
        "suggested_bin": None if unsure else SUGGESTED_BIN[predicted],
    }


def load_model(model_dir: Path | None = None):
    global _cached_model, _cached_checkpoint, _cached_path, _cached_mtime_ns
    path = _model_dir(model_dir) / "item_classifier.pt"
    if not path.is_file():
        raise ClassifierUnavailable("Classifier model not loaded on this laptop")
    mtime_ns = path.stat().st_mtime_ns
    if _cached_path == path and _cached_mtime_ns == mtime_ns and _cached_model is not None:
        return _cached_model, _cached_checkpoint
    try:
        import torch
        from torch import nn
        from torchvision.models import mobilenet_v3_small
    except ImportError as exc:
        raise ClassifierUnavailable("PyTorch or torchvision is not installed") from exc
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if (
        checkpoint.get("classes") != list(CLASSES)
        or checkpoint.get("arch") != "mobilenet_v3_small"
        or checkpoint.get("img_size") != 224
    ):
        raise ClassifierUnavailable("Classifier checkpoint has an incompatible class order")
    model = mobilenet_v3_small(weights=None)
    model.classifier[3] = nn.Linear(model.classifier[3].in_features, len(CLASSES))
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    _cached_model, _cached_checkpoint = model, checkpoint
    _cached_path, _cached_mtime_ns = path, mtime_ns
    return model, checkpoint


def classify_image(image_bytes: bytes, model_dir: Path | None = None) -> dict:
    model, checkpoint = load_model(model_dir)
    try:
        import torch
        from PIL import Image, ImageOps
        from torchvision import transforms
    except ImportError as exc:
        raise ClassifierUnavailable("Image inference dependencies are not installed") from exc
    try:
        with Image.open(io.BytesIO(image_bytes)) as raw:
            image = ImageOps.exif_transpose(raw).convert("RGB")
    except (OSError, ValueError) as exc:
        raise ValueError("Invalid image file") from exc
    transform = transforms.Compose(
        [
            transforms.Resize(256),
            transforms.CenterCrop(int(checkpoint["img_size"])),
            transforms.ToTensor(),
            transforms.Normalize(checkpoint["mean"], checkpoint["std"]),
        ]
    )
    with torch.inference_mode():
        logits = model(transform(image).unsqueeze(0))
        probs = torch.softmax(logits, dim=1)[0].tolist()
    return build_result(probs, checkpoint["classes"], CONFIDENCE_THRESHOLD)


def classifier_status(model_dir: Path | None = None) -> dict:
    directory = _model_dir(model_dir)
    model_path = directory / "item_classifier.pt"
    report_path = directory / "classifier_report.json"
    report = None
    if report_path.is_file():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            report = None
    available = model_path.is_file()
    version = report.get("model_version") if isinstance(report, dict) else None
    if available:
        try:
            _, checkpoint = load_model(directory)
        except (ClassifierUnavailable, KeyError, RuntimeError, ValueError):
            available = False
        else:
            version = checkpoint.get("model_version")
    return {
        "available": available,
        "model_version": version,
        "classes": list(CLASSES),
        "report": report,
    }
