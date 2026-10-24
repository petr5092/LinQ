"""Download and normalize the verified Atharion PPE v1.0 YOLO dataset.

Usage:
    python -m training.download_dataset
No PyTorch required. Keeps upstream metadata and license notices.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

URL = "https://github.com/atharion-team/ppe-dataset-v1/releases/download/v1.0/atharion-v1.0-public.zip"
SHA256 = "f5f6f1966c4bdfff4151ee68fa0da21f446e1b788d15280e5f70028c69ec88c5"
CLASS_NAMES = ["person", "helmet", "vest"]
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

def locate(root: Path, split: str) -> Path:
    names = ("valid", "val") if split == "val" else (split,)
    candidates = []
    for n in names:
        candidates += list(root.rglob(f"{n}/images"))
        candidates += list(root.rglob(f"images/{n}"))
    candidates = [p for p in candidates if p.is_dir() and any(
        f.is_file() and f.suffix.lower() in IMAGE_EXTS for f in p.rglob("*"))]
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one image folder for {split}; found {candidates}")
    return candidates[0]

def corresponding_label(image: Path, images_folder: Path) -> Path:
    # Supported layouts: train/images/a.jpg, images/train/a.jpg
    if images_folder.name == "images":
        label_root = images_folder.parent / "labels"
    else:
        label_root = images_folder.parent.parent / "labels" / images_folder.name
    return label_root / image.relative_to(images_folder).with_suffix(".txt")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("data/safety_dataset"))
    ap.add_argument("--archive", type=Path, default=None, help="Use previously downloaded original ZIP")
    args = ap.parse_args()
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        ap.error(f"Output folder is not empty: {out}")
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="linq_ppe_") as tmp:
        tmpdir = Path(tmp)
        archive = args.archive.resolve() if args.archive else tmpdir / "source.zip"
        if not args.archive:
            print(f"Downloading {URL}", flush=True)
            urllib.request.urlretrieve(URL, archive)
        h = hashlib.sha256()
        with archive.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        if h.hexdigest() != SHA256:
            raise RuntimeError("SHA256 mismatch: dataset archive is not the verified release")
        with zipfile.ZipFile(archive) as zf:
            extracted = tmpdir / "extract"
            extracted.mkdir()
            for member in zf.infolist():
                target = (extracted / member.filename).resolve()
                if not target.is_relative_to(extracted.resolve()):
                    raise RuntimeError("Unsafe ZIP path")
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, target.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
        stats = {}
        for split in ("train", "val", "test"):
            source_images = locate(extracted, split)
            dest_images = out / "images" / split
            dest_labels = out / "labels" / split
            dest_images.mkdir(parents=True)
            dest_labels.mkdir(parents=True)
            count = 0
            for image in sorted(source_images.rglob("*")):
                if not image.is_file() or image.suffix.lower() not in IMAGE_EXTS:
                    continue
                rel = image.relative_to(source_images)
                dest_image = dest_images / rel
                dest_image.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(image, dest_image)
                source_label = corresponding_label(image, source_images)
                if source_label.is_file():
                    dest_label = dest_labels / rel.with_suffix(".txt")
                    dest_label.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_label, dest_label)
                count += 1
            stats[split] = count
        # The upstream class IDs are 0 Person, 1 Hardhat, 2 Safety Vest.
        # We normalize spelling without changing numeric IDs.
        import yaml
        (out / "data.yaml").write_text(yaml.safe_dump({
            "path": ".", "train": "images/train", "val": "images/val",
            "test": "images/test", "names": CLASS_NAMES
        }, sort_keys=False), encoding="utf-8")
        for name in ("NOTICE.md", "DATASET_CARD.md", "LICENSE", "attribution.csv"):
            found = list(extracted.rglob(name))
            if found:
                shutil.copy2(found[0], out / name)
        (out / "source_manifest.json").write_text(json.dumps({
            "source": URL, "source_sha256": SHA256,
            "original_classes": ["Person", "Hardhat", "Safety Vest"],
            "normalized_classes": CLASS_NAMES, "counts": stats,
            "license_note": "Mixed AGPL-3.0 and CC BY 4.0; see upstream NOTICE.md.",
        }, indent=2), encoding="utf-8")
        from training.validate_dataset import validate_dataset
        report = validate_dataset(out / "data.yaml")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"Dataset prepared: {out}")

if __name__ == "__main__":
    main()
