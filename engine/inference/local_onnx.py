"""Explicit local CPU inference for static raw YOLO detection ONNX exports."""

from __future__ import annotations

import ast
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    ort = None

from engine.inference.base import BaseInferenceEngine, Detection, InferenceMetrics, InferenceResult
from engine.inference.yolo import decode_yolo, letterbox, nms_indices


class LocalONNXEngine(BaseInferenceEngine):
    def __init__(self, model_path: Optional[str] = None, conf_threshold: float = 0.35,
                 iou_threshold: float = 0.45, input_size: Tuple[int, int] = (640, 640),
                 class_names: Optional[Dict[int, str]] = None, providers: Optional[List[str]] = None):
        super().__init__(model_path, conf_threshold, iou_threshold, input_size, class_names)
        self.providers = providers or ["CPUExecutionProvider"]
        if self.providers != ["CPUExecutionProvider"]:
            raise ValueError("ONNX_CPU requires CPUExecutionProvider; other providers need their own backend.")
        self._configured_class_names = self.class_names.copy()
        self.session = None
        self.input_name = ""
        self.output_names = []
        if self.model_path is not None:
            self.load()

    def load(self, model_path: Optional[str] = None) -> None:
        path = model_path or self.model_path
        self.close()
        if not path:
            raise ValueError("ONNX model path is required.")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"ONNX model not found: {path}. Use INFERENCE_BACKEND=MOCK only for tests.")
        if ort is None:
            raise RuntimeError("onnxruntime is not installed.")
        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        options.intra_op_num_threads = max(1, os.cpu_count() or 4)
        session = ort.InferenceSession(str(path), sess_options=options, providers=self.providers)
        inputs, outputs = session.get_inputs(), session.get_outputs()
        if len(inputs) != 1 or len(outputs) != 1:
            raise ValueError("Expected one input and one raw detection output; export YOLO with nms=False.")
        shape = inputs[0].shape
        if (len(shape) != 4 or shape[:2] != [1, 3]
                or any(type(dim) is not int or dim <= 0 for dim in shape)
                or inputs[0].type != "tensor(float)"):
            raise ValueError(f"Expected static float32 NCHW [1, 3, H, W] input; found {shape}, {inputs[0].type}.")
        metadata = session.get_modelmeta().custom_metadata_map
        class_names = self._configured_class_names.copy()
        if metadata.get("names"):
            try:
                model_names = self.validate_class_names(ast.literal_eval(metadata["names"]))
            except (ValueError, SyntaxError, TypeError) as exc:
                raise ValueError("Invalid 'names' metadata in ONNX model.") from exc
            if class_names and class_names != model_names:
                raise ValueError("Configured class_names disagree with ONNX names metadata; check the trained model.")
            class_names = model_names
        if not class_names:
            raise ValueError("ONNX model has no class names; supply the complete class_names mapping.")
        if metadata.get("task", "detect") != "detect":
            raise ValueError("Only YOLO detection models are supported; pose/segment/classify need a different decoder.")
        output_shape = outputs[0].shape
        attrs = 4 + len(class_names)
        if (len(output_shape) != 3 or output_shape[0] != 1
                or sum(dim == attrs for dim in output_shape[1:]) != 1):
            raise ValueError(f"Output {output_shape} does not match {len(class_names)} classes / raw YOLO detection format.")
        self.input_size = (shape[3], shape[2])
        self.class_names = class_names
        self.input_name = inputs[0].name
        self.output_names = [outputs[0].name]
        self.model_path = path
        self.session = session
        self.is_loaded = True

    def preprocess(self, frame: np.ndarray):
        return letterbox(frame, self.input_size)

    def postprocess(self, raw_output: Any, meta: Dict[str, Any]) -> List[Detection]:
        return decode_yolo(raw_output, meta, self.class_names, self.conf_threshold, self.iou_threshold)

    _nms_indices = staticmethod(nms_indices)

    def infer(self, frame: np.ndarray) -> InferenceResult:
        if not self.is_loaded or self.session is None:
            raise RuntimeError("ONNX model is not loaded. Call load() before infer().")
        t0 = time.perf_counter()
        tensor, meta = self.preprocess(frame)
        t1 = time.perf_counter()
        outputs = self.session.run(self.output_names, {self.input_name: tensor})
        t2 = time.perf_counter()
        detections = self.postprocess(outputs, meta)
        t3 = time.perf_counter()
        total_ms = (t3 - t0) * 1000
        return InferenceResult(detections, InferenceMetrics(
            preprocess_time_ms=(t1 - t0) * 1000, inference_time_ms=(t2 - t1) * 1000,
            postprocess_time_ms=(t3 - t2) * 1000, total_time_ms=total_ms,
            fps=1000 / total_ms if total_ms else 0.0, backend_name="ONNX_CPU",
        ), frame.shape)

    def close(self) -> None:
        self.session = None
        super().close()
