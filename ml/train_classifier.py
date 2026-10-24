"""Fine-tune a six-output MobileNetV3 Small for five bins plus battery safety."""

from __future__ import annotations

import argparse
import csv
import hashlib
import random
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from prepare_dataset import CLASSES


IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    required = {"path", "source", "original_label", "target_class", "md5"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Manifest has no rows or misses columns: {sorted(required)}")
    unknown = sorted({row["target_class"] for row in rows} - set(CLASSES))
    if unknown:
        raise ValueError(f"Unknown target classes: {unknown}")
    if len({row["md5"] for row in rows}) != len(rows):
        raise ValueError("Manifest still contains duplicate image hashes")
    return rows


def manifest_fingerprint(rows: list[dict[str, str]]) -> str:
    canonical = sorted((r["source"], r["target_class"], r["md5"]) for r in rows)
    content = "\n".join("\t".join(row) for row in canonical).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def split_records(rows: list[dict[str, str]], holdout_source: str = "realwaste", seed: int = 0):
    """Return deterministic, class-stratified train/val/test/shift partitions."""
    from sklearn.model_selection import train_test_split

    trainable = [row for row in rows if row["source"] != holdout_source]
    shift = [row for row in rows if row["source"] == holdout_source]
    if not shift:
        raise ValueError(f"Holdout source {holdout_source!r} is absent from the manifest")
    counts = Counter(row["target_class"] for row in trainable)
    sparse = {name: counts[name] for name in CLASSES if counts[name] < 10}
    if sparse:
        raise ValueError(f"At least 10 training-source images per class are needed: {sparse}")
    labels = [row["target_class"] for row in trainable]
    train, remainder = train_test_split(
        trainable, test_size=0.2, random_state=seed, stratify=labels
    )
    val, test = train_test_split(
        remainder,
        test_size=0.5,
        random_state=seed,
        stratify=[row["target_class"] for row in remainder],
    )
    return train, val, test, shift


def make_transforms(train: bool):
    from torchvision import transforms

    if train:
        steps = [
            transforms.RandomResizedCrop(224),
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(0.2, 0.2, 0.2),
        ]
    else:
        steps = [transforms.Resize(256), transforms.CenterCrop(224)]
    return transforms.Compose(
        steps + [transforms.ToTensor(), transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD)]
    )


class ImageRows:
    def __init__(self, rows: list[dict[str, str]], transform):
        self.rows = rows
        self.transform = transform

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        from PIL import Image

        row = self.rows[index]
        with Image.open(row["path"]) as raw:
            image = raw.convert("RGB")
        return self.transform(image), CLASSES.index(row["target_class"])


def evaluate_accuracy(model, loader, device) -> float:
    import torch

    model.eval()
    correct = total = 0
    with torch.inference_mode():
        for images, labels in loader:
            logits = model(images.to(device))
            correct += int((logits.argmax(1).cpu() == labels).sum())
            total += len(labels)
    return correct / total if total else 0.0


def train(args) -> Path:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader
    from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

    rows = read_manifest(args.manifest)
    train_rows, val_rows, test_rows, shift_rows = split_records(rows, args.holdout_source, args.seed)
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"CUDA available: {torch.cuda.is_available()} | device: {device}")
    print(
        f"Split: train={len(train_rows)}, val={len(val_rows)}, "
        f"random_test={len(test_rows)}, shift_test={len(shift_rows)}"
    )
    counts = Counter(row["target_class"] for row in train_rows)
    weights = [1.0 / counts[label] for label in CLASSES]
    mean_weight = sum(weights) / len(weights)
    weights = torch.tensor([weight / mean_weight for weight in weights], dtype=torch.float32, device=device)
    train_loader = DataLoader(
        ImageRows(train_rows, make_transforms(True)),
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
    )
    val_loader = DataLoader(
        ImageRows(val_rows, make_transforms(False)),
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
    )
    model = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.DEFAULT)
    model.classifier[3] = nn.Linear(model.classifier[3].in_features, len(CLASSES))
    model.to(device)
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    best_accuracy = -1.0
    best_epoch = 0
    best_state = None
    for epoch in range(1, args.epochs + 1):
        started = time.perf_counter()
        model.train()
        running_loss = 0.0
        n_seen = 0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images), labels)
            loss.backward()
            optimizer.step()
            running_loss += float(loss) * len(labels)
            n_seen += len(labels)
        val_accuracy = evaluate_accuracy(model, val_loader, device)
        elapsed = time.perf_counter() - started
        print(
            f"epoch {epoch}/{args.epochs}: train_loss={running_loss / n_seen:.4f} "
            f"val_accuracy={val_accuracy:.4f} seconds={elapsed:.1f}",
            flush=True,
        )
        if val_accuracy > best_accuracy:
            best_accuracy = val_accuracy
            best_epoch = epoch
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
    assert best_state is not None
    args.out_dir.mkdir(parents=True, exist_ok=True)
    output = args.out_dir / "item_classifier.pt"
    torch.save(
        {
            "state_dict": best_state,
            "classes": list(CLASSES),
            "arch": "mobilenet_v3_small",
            "img_size": 224,
            "mean": list(IMAGENET_MEAN),
            "std": list(IMAGENET_STD),
            "model_version": "mnv3s-" + datetime.now(timezone.utc).strftime("%Y%m%d"),
        },
        output,
    )
    print(f"Saved {output} (best epoch {best_epoch}, validation accuracy {best_accuracy:.4f})")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--holdout-source", default="realwaste")
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--out-dir", type=Path, default=Path("/kaggle/working"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--num-workers", type=int, default=2)
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.num_workers < 0 or args.lr <= 0:
        parser.error("epochs, batch-size and lr must be positive; num-workers must be nonnegative")
    train(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
