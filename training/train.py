"""Train an Ultralytics detection model. No imports of the web backend."""
from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path

def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="LinQ Safety detector fine-tuning")
    p.add_argument("--data", type=Path, required=True, help="YOLO dataset YAML")
    p.add_argument("--weights", default="yolov8s.pt", help="Pretrained .pt weights")
    p.add_argument("--epochs", type=int, default=100)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--batch", type=int, default=8)
    p.add_argument("--device", default="0", help="CUDA index, cpu or mps")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--project", default="runs/linq")
    p.add_argument("--name", default="safety")
    p.add_argument("--patience", type=int, default=25)
    p.add_argument("--check-only", action="store_true")
    return p

def main() -> None:
    args = parser().parse_args()
    if not args.data.is_file():
        parser().error(f"Dataset YAML missing: {args.data}")
    if args.epochs < 1 or args.imgsz < 32 or args.batch < 1:
        parser().error("epochs and batch must be positive; imgsz >= 32")
    from training.validate_dataset import validate_dataset
    report = validate_dataset(args.data)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.check_only:
        return

    import torch
    if args.device != "cpu" and args.device != "mps":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable on this host. Run on a GPU trainer or use --device cpu.")
        index = int(args.device.split(",")[0])
        if index >= torch.cuda.device_count():
            raise RuntimeError(f"CUDA GPU {index} not found")

    from ultralytics import YOLO
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    model = YOLO(args.weights)
    results = model.train(
        data=str(args.data.resolve()),
        task="detect",
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        seed=args.seed,
        deterministic=True,
        pretrained=True,
        patience=args.patience,
        optimizer="AdamW",
        cos_lr=True,
        close_mosaic=10,
        project=args.project,
        name=args.name,
        exist_ok=False,
        plots=True,
    )
    run_dir = Path(model.trainer.save_dir)
    best = run_dir / "weights" / "best.pt"
    if not best.is_file():
        raise RuntimeError(f"Missing best checkpoint after training: {best}")
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "weights_source": args.weights,
        "best_checkpoint": str(best.resolve()),
        "data_yaml": str(args.data.resolve()),
        "classes": report["classes"],
        "seed": args.seed,
        "training": {"epochs": args.epochs, "imgsz": args.imgsz, "batch": args.batch, "device": args.device},
        "torch_version": torch.__version__,
    }
    (run_dir / "linq_training_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Training complete. Best weights: {best}")
    print("Test split has NOT been evaluated; run evaluation once after model selection.")

if __name__ == "__main__":
    main()
