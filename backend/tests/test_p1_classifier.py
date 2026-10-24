"""P1 classifier safety and upload behavior."""

from io import BytesIO

from PIL import Image

from app import config
from app.classifier.infer import CLASSES, build_result


def test_battery_unsure_and_organic_advice():
    classes = list(CLASSES)
    battery = build_result([0.8, 0.04, 0.04, 0.04, 0.04, 0.04], classes)
    assert battery["predicted_class"] == "battery"
    assert battery["hazardous"] is True
    assert battery["suggested_bin"] == "Hazardous - hand over for special pickup"
    uncertain = build_result([1 / 6] * 6, classes)
    assert uncertain["unsure"] is True
    assert uncertain["suggested_bin"] is None
    organic = build_result([0.02, 0.02, 0.9, 0.02, 0.02, 0.02], classes)
    assert organic["suggested_bin"] == "Wet waste - food and organic"


def test_upload_validation_and_missing_model(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MODEL_DIR", tmp_path)
    image = BytesIO()
    Image.new("RGB", (8, 8), "white").save(image, format="PNG")
    valid = image.getvalue()
    response = client.post("/api/classify", files={
        "photo": ("item.png", valid, "image/png"),
    })
    assert response.status_code == 503
    assert response.json() == {"detail": "Classifier model not available"}
    assert client.post("/api/classify", files={
        "photo": ("item.txt", b"not an image", "text/plain"),
    }).status_code == 400
    assert client.post("/api/classify").status_code == 400
