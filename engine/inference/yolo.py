"""Shared preprocessing and decoding for raw YOLOv8/v9/v11 detection exports.

Contract: RGB float32 NCHW [0, 1], xywh boxes in input pixels, class
probabilities without objectness. Segmentation, pose and end-to-end/NMS exports
are deliberately rejected instead of being interpreted as ordinary detections.
"""

from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

from engine.inference.base import BoundingBox, Detection


def letterbox(frame: np.ndarray, input_size: Tuple[int, int]):
    if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("Expected a BGR image with shape (H, W, 3).")
    if frame.dtype != np.uint8 or not frame.shape[0] or not frame.shape[1]:
        raise ValueError("Expected a nonempty uint8 BGR image.")
    orig_h, orig_w = frame.shape[:2]
    target_w, target_h = input_size
    scale = min(target_w / orig_w, target_h / orig_h)
    new_w = max(1, int(round(orig_w * scale)))
    new_h = max(1, int(round(orig_h * scale)))
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    left = (target_w - new_w) // 2
    top = (target_h - new_h) // 2
    padded = cv2.copyMakeBorder(
        resized, top, target_h - new_h - top, left, target_w - new_w - left,
        cv2.BORDER_CONSTANT, value=(114, 114, 114),
    )
    tensor = np.ascontiguousarray(padded[:, :, ::-1].transpose(2, 0, 1)[None], dtype=np.float32)
    tensor /= 255.0
    return tensor, {
        "orig_shape": (orig_h, orig_w), "scale": scale,
        # Use the actual resize and integer border, including odd padding.
        "scale_x": new_w / orig_w, "scale_y": new_h / orig_h,
        "pad_x": left, "pad_y": top,
    }


def nms_indices(x1, y1, x2, y2, scores, iou_thresh) -> List[int]:
    areas = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size:
        i = order[0]
        keep.append(int(i))
        rest = order[1:]
        inter = np.maximum(0.0, np.minimum(x2[i], x2[rest]) - np.maximum(x1[i], x1[rest])) * np.maximum(
            0.0, np.minimum(y2[i], y2[rest]) - np.maximum(y1[i], y1[rest])
        )
        union = areas[i] + areas[rest] - inter
        iou = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)
        order = rest[iou <= iou_thresh]
    return keep


def decode_yolo(raw_output: Any, meta: Dict, class_names: Dict[int, str], conf_threshold: float,
                iou_threshold: float, output_name: str = "output0") -> List[Detection]:
    if not class_names:
        raise ValueError("Model class names are required: use ONNX names metadata or explicit class_names.")
    if isinstance(raw_output, dict):
        if output_name not in raw_output:
            raise ValueError(f"Missing output node {output_name!r}; available: {list(raw_output)}")
        raw_output = raw_output[output_name]
    if isinstance(raw_output, (list, tuple)):
        if len(raw_output) != 1:
            raise ValueError("Expected one raw YOLO detection output; multi-head exports need a custom decoder.")
        raw_output = raw_output[0]
    output = np.asarray(raw_output)
    if output.ndim == 3 and output.shape[0] == 1:
        output = output[0]
    attrs = 4 + len(class_names)
    if output.ndim != 2 or sum(size == attrs for size in output.shape) != 1:
        raise ValueError(
            f"Unsupported or ambiguous YOLO output shape {output.shape}; expected [1, {attrs}, N] "
            f"or [1, N, {attrs}] for {len(class_names)} classes (raw export, nms=False)."
        )
    if output.shape[0] == attrs:
        output = output.T
    if not np.issubdtype(output.dtype, np.floating):
        raise ValueError("YOLO output must be floating point; the TPU adapter must dequantize it.")
    if not len(output):
        return []
    # Invalid candidates must never create synthetic alerts.
    valid = np.isfinite(output).all(axis=1) & (output[:, 2:4] > 0).all(axis=1)
    output = output[valid]
    if not len(output):
        return []
    class_scores = output[:, 4:]
    if np.any((class_scores < 0) | (class_scores > 1)):
        raise ValueError("Expected YOLO class probabilities in [0, 1], not logits or quantized output.")
    scores = class_scores.max(axis=1)
    ids = class_scores.argmax(axis=1)
    selected = scores >= conf_threshold
    boxes, scores, ids = output[selected, :4], scores[selected], ids[selected]
    xyxy = np.empty_like(boxes)
    xyxy[:, :2] = boxes[:, :2] - boxes[:, 2:] / 2
    xyxy[:, 2:] = boxes[:, :2] + boxes[:, 2:] / 2
    scale_x = meta.get("scale_x", meta["scale"])
    scale_y = meta.get("scale_y", meta["scale"])
    xyxy[:, [0, 2]] = (xyxy[:, [0, 2]] - meta["pad_x"]) / scale_x
    xyxy[:, [1, 3]] = (xyxy[:, [1, 3]] - meta["pad_y"]) / scale_y
    orig_h, orig_w = meta["orig_shape"]
    xyxy[:, [0, 2]] = xyxy[:, [0, 2]].clip(0, orig_w)
    xyxy[:, [1, 3]] = xyxy[:, [1, 3]].clip(0, orig_h)
    detections = []
    for class_id in np.unique(ids):
        indices = np.flatnonzero(ids == class_id)
        coords, confidences = xyxy[indices], scores[indices]
        for idx in nms_indices(*coords.T, confidences, iou_threshold):
            bbox = BoundingBox(*map(float, coords[idx]))
            if bbox.area:
                detections.append(Detection(bbox, float(confidences[idx]), int(class_id), class_names[int(class_id)]))
    return sorted(detections, key=lambda detection: detection.confidence, reverse=True)
