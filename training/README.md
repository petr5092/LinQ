# LinQ CV — detector training

This module is **independent of the web backend**. It fine-tunes a YOLOv8 detect model,
validates a standard YOLO dataset and exports a raw detect ONNX for the existing
`feature/cv-pipeline` inference adapter. It does not train on LinQ TPU; LinQ TPU
is used downstream for inference.

## Dataset layout

```
data/safety_dataset/
  data.yaml
  images/{train,val,test}/*.jpg
  labels/{train,val,test}/*.txt
```

`data.yaml` example (path is relative to the YAML file):

```yaml
path: .
train: images/train
val: images/val
test: images/test
names: [person, helmet, vest]
```

YOLO labels: `class_id x_center y_center width height` with normalized
coordinates. Missing label TXT is allowed for verified negative images.
**These names are examples, not verified labels for your dataset.**
For danger-zone-only detection, you can use `names: [person]` and a matching
one-class checkpoint/training set. Do not pretend COCO labels are PPE labels.

Split by original camera and video before extracting frames. The validator checks
exact duplicate image bytes across splits, but cannot detect near-duplicate frames
or camera leakage.

## Setup on a separate GPU training machine

Use Python 3.11/3.12, install a compatible **CUDA-enabled PyTorch** first from
[PyTorch installation](https://pytorch.org/get-started/locally/), then:

```bash
python -m pip install -r training/requirements.txt
python -m training.validate_dataset --data data/safety_dataset/data.yaml
python -m training.train --data data/safety_dataset/data.yaml --weights yolov8s.pt --epochs 100 --imgsz 640 --batch 8 --device 0
```

A dry dataset check without torch:

```bash
python -m training.train --data data/safety_dataset/data.yaml --check-only
```

The trainer writes `runs/linq/safety*/weights/best.pt` and a manifest.
Select hyperparameters on validation; run test only after model selection:

```bash
python -m training.evaluate_export --weights runs/linq/safety/weights/best.pt --data data/safety_dataset/data.yaml --split val --device 0 --export --out models/onnx/safety_yolov8.onnx
python -m training.evaluate_export --weights runs/linq/safety/weights/best.pt --data data/safety_dataset/data.yaml --split test --device 0
```

The ONNX export is batch 1 / fixed 640 / raw detect / no NMS. Inspect outputs
with `python -m linq_tools.inspect_onnx models/onnx/safety_yolov8.onnx`
before using the existing TPU compilation tool. SDK support for opset 12,
head operations and quantization must be tested on the actual SDK/device.

Do not commit private training footage, pretrained weights, credentials or
large binaries to Git. Train on a GPU host; VPN+Jupyter provided for LinQ
inference is **not confirmed** to provide a GPU training service.
