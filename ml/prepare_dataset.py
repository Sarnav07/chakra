"""Build a source-aware image manifest for CHAKRA's item classifier.

RealWaste is a held-out domain test. Exact duplicate images found in that
source are removed from training sources, regardless of source argument order.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path


CLASSES = ("battery", "metal", "organic", "other", "paper", "plastic")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
DEFAULT_MAP = {
    "paper": "paper",
    "cardboard": "paper",
    "plastic": "plastic",
    "metal": "metal",
    "biological": "organic",
    "food organics": "organic",
    "vegetation": "organic",
    "trash": "other",
    "misc trash": "other",
    "miscellaneous trash": "other",
    "glass": "other",
    "green glass": "other",
    "brown glass": "other",
    "white glass": "other",
    "clothes": "other",
    "shoes": "other",
    "textile trash": "other",
    "battery": "battery",
    "batteries": "battery",
}
SOURCE_NAMES = {"kaggle12", "realwaste", "trashnet"}


def normalize_label(value: str) -> str:
    return "_".join(value.strip().lower().replace("-", " ").replace("_", " ").split())


def parse_pair(value: str, *, kind: str) -> tuple[str, str]:
    if "=" not in value:
        raise ValueError(f"{kind} must be NAME=VALUE: {value!r}")
    name, target = value.split("=", 1)
    if not name.strip() or not target.strip():
        raise ValueError(f"{kind} must be NAME=VALUE: {value!r}")
    return name.strip(), target.strip()


def image_folders(root: Path):
    if not root.is_dir():
        raise ValueError(f"Dataset directory does not exist: {root}")
    for folder in sorted(p for p in root.rglob("*") if p.is_dir()):
        images = sorted(
            (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES),
            key=lambda p: str(p).lower(),
        )
        if images:
            yield folder, images
    root_images = sorted(
        (p for p in root.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES),
        key=lambda p: str(p).lower(),
    )
    if root_images:
        yield root, root_images


def file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare(sources: dict[str, Path], label_map: dict[str, str], output: Path) -> dict:
    if not sources:
        raise ValueError("Provide at least one --source NAME=PATH")
    candidates = []
    unknown = defaultdict(int)
    for source, root in sources.items():
        if source not in SOURCE_NAMES:
            raise ValueError(f"Unknown source {source!r}; use {', '.join(sorted(SOURCE_NAMES))}")
        if source == "kaggle12" and (root / "garbage_classification_corrected").is_dir() and (
            root / "garbage_classification_enhanced"
        ).is_dir():
            raise ValueError(
                "Point kaggle12 at garbage_classification_enhanced, not the parent folder "
                "that also contains garbage_classification_corrected"
            )
        for folder, images in image_folders(root):
            original = folder.name
            target = label_map.get(normalize_label(original))
            if target is None:
                unknown[(source, original)] += len(images)
                continue
            for path in images:
                candidates.append((source, original, target, path))
    if unknown:
        lines = ["Unmapped label folders (add --map FOLDER=CLASS; no manifest written):"]
        lines.extend(
            f"  {source}/{label}: {count} images"
            for (source, label), count in sorted(unknown.items())
        )
        raise ValueError("\n".join(lines))

    # Hash before splitting, and retain RealWaste when a byte-identical image
    # appears in both training and holdout sources.
    hashed = [(source, original, target, path, file_md5(path)) for source, original, target, path in candidates]
    hashed.sort(key=lambda row: (row[0] != "realwaste", row[0], str(row[3]).lower()))
    seen = set()
    kept = []
    dropped = Counter()
    for source, original, target, path, md5 in hashed:
        if md5 in seen:
            dropped[source] += 1
            continue
        seen.add(md5)
        kept.append((str(path.resolve()), source, original, target, md5))
    kept.sort(key=lambda row: (row[1], row[2].lower(), row[0].lower()))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("path", "source", "original_label", "target_class", "md5"))
        writer.writerows(kept)
    counts = Counter((source, target) for _, source, _, target, _ in kept)
    print(f"Manifest: {output} ({len(kept)} images; {sum(dropped.values())} duplicate copies removed)")
    for source in sorted(sources):
        print(f"{source}: " + ", ".join(f"{label}={counts[source, label]}" for label in CLASSES))
    return {"n_images": len(kept), "counts": counts, "duplicates_removed": dict(dropped)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--map", action="append", default=[], metavar="FOLDER=CLASS")
    parser.add_argument("--out", required=True, type=Path, metavar="CSV")
    args = parser.parse_args()
    try:
        sources = {}
        for entry in args.source:
            name, path = parse_pair(entry, kind="source")
            if name in sources:
                raise ValueError(f"Duplicate source name: {name}")
            sources[name] = Path(path)
        label_map = {normalize_label(name): target for name, target in DEFAULT_MAP.items()}
        for entry in args.map:
            folder, target = parse_pair(entry, kind="map")
            target = normalize_label(target)
            if target not in CLASSES:
                raise ValueError(f"Unknown target class {target!r}; use {', '.join(CLASSES)}")
            label_map[normalize_label(folder)] = target
        prepare(sources, label_map, args.out)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
