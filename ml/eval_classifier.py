"""Evaluate CHAKRA's classifier on random, source-shift, and campus photos."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from prepare_dataset import CLASSES, IMAGE_SUFFIXES, normalize_label
from train_classifier import (
    ImageRows,
    make_transforms,
    read_manifest,
    split_records,
)


def campus_rows(directory: Path) -> list[dict[str, str]]:
    if not directory.is_dir():
        raise ValueError(f"Campus photo directory does not exist: {directory}")
    rows = []
    for folder in sorted(p for p in directory.iterdir() if p.is_dir()):
        label = normalize_label(folder.name)
        if label not in CLASSES:
            raise ValueError(f"Unknown campus folder {folder.name!r}; use one of {', '.join(CLASSES)}")
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                rows.append({"path": str(path), "target_class": label, "source": "campus"})
    if not rows:
        raise ValueError(f"No labeled campus images found in {directory}")
    return rows


def evaluate_set(model, rows, device, batch_size: int) -> dict:
    import torch
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
    from torch.utils.data import DataLoader

    loader = DataLoader(ImageRows(rows, make_transforms(False)), batch_size=batch_size, shuffle=False)
    actual = []
    predicted = []
    model.eval()
    with torch.inference_mode():
        for images, labels in loader:
            output = model(images.to(device))
            predicted.extend(output.argmax(1).cpu().tolist())
            actual.extend(labels.tolist())
    indices = list(range(len(CLASSES)))
    counts = Counter(actual)
    return {
        "n_images": len(rows),
        "accuracy": float(accuracy_score(actual, predicted)),
        "per_class": classification_report(
            actual,
            predicted,
            labels=indices,
            target_names=list(CLASSES),
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(actual, predicted, labels=indices).tolist(),
        "label_order": list(CLASSES),
        "absent_classes": [CLASSES[index] for index in indices if counts[index] == 0],
    }


def evaluate(args) -> dict:
    import torch
    from torch import nn
    from torchvision.models import mobilenet_v3_small

    rows = read_manifest(args.manifest)
    checkpoint = torch.load(args.model, map_location="cpu", weights_only=True)
    if checkpoint.get("classes") != list(CLASSES):
        raise ValueError("Checkpoint class order differs from the six-class CHAKRA contract")
    holdout_source = args.holdout_source
    _, _, random_test, shift_test = split_records(rows, holdout_source, args.seed)
    model = mobilenet_v3_small(weights=None)
    model.classifier[3] = nn.Linear(model.classifier[3].in_features, len(CLASSES))
    model.load_state_dict(checkpoint["state_dict"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    report = {
        "model_version": checkpoint["model_version"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classes": list(CLASSES),
        "holdout_source": holdout_source,
        "random_test": evaluate_set(model, random_test, device, args.batch_size),
        "shift_test": evaluate_set(model, shift_test, device, args.batch_size),
    }
    if args.campus_dir:
        report["campus_test"] = evaluate_set(model, campus_rows(args.campus_dir), device, args.batch_size)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for name in ("random_test", "shift_test", "campus_test"):
        if name in report:
            metrics = report[name]
            print(f"{name}: n={metrics['n_images']} accuracy={metrics['accuracy']:.4f} absent={metrics['absent_classes']}")
    print(f"Saved {args.out}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--holdout-source", default="realwaste")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--campus-dir", type=Path)
    parser.add_argument("--out", type=Path, default=Path("classifier_report.json"))
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()
    evaluate(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
