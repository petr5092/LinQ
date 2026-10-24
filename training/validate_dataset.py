"""Preflight checks for a YOLO detection dataset (no torch required)."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import yaml

EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

def validate_dataset(config: Path) -> dict:
    config = config.resolve()
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    if not isinstance(cfg, dict):
        raise ValueError("Dataset YAML must be a mapping")
    classes = cfg.get("names")
    if isinstance(classes, dict):
        classes = [classes[k] if k in classes else classes.get(str(k)) for k in range(len(classes))]
    if not isinstance(classes, list) or not classes or not all(isinstance(c, str) and c.strip() for c in classes):
        raise ValueError("names must be a non-empty sequence of class names")
    if len(set(classes)) != len(classes):
        raise ValueError("Duplicate class names")
    root = Path(cfg.get("path", "."))
    root = (config.parent / root).resolve() if not root.is_absolute() else root.resolve()
    counts = {}
    fingerprints = {}
    for split in ("train", "val", "test"):
        rel = cfg.get(split)
        if split == "test" and rel is None:
            continue
        if not isinstance(rel, str):
            raise ValueError(f"Missing/invalid {split} image directory")
        folder = (root / rel).resolve()
        if not folder.is_dir():
            raise FileNotFoundError(f"{split} images not found: {folder}")
        images = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in EXTS)
        if not images:
            raise ValueError(f"No images in {folder}")
        stats = Counter()
        stats["images"] = len(images)
        for image in images:
            # Standard YOLO structure: images/<split>/x.jpg -> labels/<split>/x.txt
            parts = list(image.parts)
            positions = [i for i, part in enumerate(parts) if part == "images"]
            if not positions:
                raise ValueError(f"Image path must contain 'images': {image}")
            parts[positions[-1]] = "labels"
            label = Path(*parts).with_suffix(".txt")
            if not label.is_file():
                stats["unlabeled_images"] += 1
            else:
                for line_idx, line in enumerate(label.read_text(encoding="utf-8").splitlines(), 1):
                    if not line.strip():
                        continue
                    parts_line = line.split()
                    if len(parts_line) != 5:
                        raise ValueError(f"Bad YOLO label {label}:{line_idx}: expected 5 columns")
                    try:
                        values = [float(x) for x in parts_line]
                    except ValueError as ex:
                        raise ValueError(f"Non-numeric label {label}:{line_idx}") from ex
                    cls, x, y, w, h = values
                    if not cls.is_integer() or not 0 <= int(cls) < len(classes):
                        raise ValueError(f"Invalid class ID in {label}:{line_idx}")
                    if not all(0 <= v <= 1 for v in (x, y, w, h)) or w <= 0 or h <= 0:
                        raise ValueError(f"Invalid normalized box in {label}:{line_idx}")
                    if x - w / 2 < -1e-5 or y - h / 2 < -1e-5 or x + w / 2 > 1.00001 or y + h / 2 > 1.00001:
                        raise ValueError(f"Box outside image in {label}:{line_idx}")
                    stats[f"class_{int(cls)}"] += 1
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            earlier = fingerprints.get(digest)
            if earlier is not None and earlier != split:
                raise ValueError(f"Exact image leakage between {earlier} and {split}: {image}")
            fingerprints[digest] = split
        counts[split] = dict(stats)
    return {"dataset_root": str(root), "classes": classes, "splits": counts,
            "note": "Exact-duplicate check only: also split by camera/video to prevent temporal leakage."}

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(validate_dataset(args.data), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
