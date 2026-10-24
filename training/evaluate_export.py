"""Evaluate a fixed checkpoint and export a raw YOLO detect ONNX model."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--weights", type=Path, required=True)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--split", choices=("val", "test"), default="val")
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--device", default="cpu")
    p.add_argument("--out", type=Path, default=Path("models/onnx/safety_yolov8.onnx"))
    p.add_argument("--export", action="store_true")
    args = p.parse_args()
    if not args.weights.is_file() or not args.data.is_file():
        p.error("Weights and dataset YAML must exist")
    from training.validate_dataset import validate_dataset
    report = validate_dataset(args.data)
    from ultralytics import YOLO
    model = YOLO(str(args.weights))
    model_names = [model.names[i] for i in range(len(model.names))]
    if model_names != report["classes"]:
        raise ValueError(f"Model class order {model_names} != dataset classes {report['classes']}")
    result = model.val(data=str(args.data.resolve()), split=args.split, imgsz=args.imgsz, device=args.device, plots=True)
    metrics = {"split": args.split, "mAP50": float(result.box.map50),
               "mAP50_95": float(result.box.map), "precision_per_class": result.box.p.tolist(),
               "recall_per_class": result.box.r.tolist(), "classes": report["classes"]}
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    if args.export:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        exported = Path(model.export(format="onnx", imgsz=args.imgsz, batch=1,
                                     dynamic=False, nms=False, opset=12))
        shutil.copy2(exported, args.out)
        args.out.with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        print(f"Exported: {args.out}")
        print("Compile and benchmark on LinQ TPU separately; ONNX export does not guarantee compatibility.")

if __name__ == "__main__":
    main()
