"""LinQ HAL with an explicit adapter for the organizer's installed SDK version.

The default linq_adapter follows the official Python API example. Its device
execution still needs validation with the compiled model on the organizer stand.
"""

from __future__ import annotations

import importlib
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from engine.inference.base import BaseInferenceEngine, Detection, InferenceMetrics, InferenceResult
from engine.inference.yolo import decode_yolo, letterbox, nms_indices


class LinQTPUEngine(BaseInferenceEngine):
    """Requires adapter_module.load(program_path) returning a callable runtime.

    The callable accepts float32 RGB NCHW input and returns dequantized raw YOLO
    detections. It must block until device inference and output transfer finish.
    Optional runtime.close() releases device resources. See linq_adapter_template.py.
    """

    def __init__(self, model_path: Optional[str] = None, conf_threshold: float = 0.35,
                 iou_threshold: float = 0.45, input_size: Tuple[int, int] = (640, 640),
                 class_names: Optional[Dict[int, str]] = None,
                 adapter_module: Optional[str] = None, output_node_name: str = "output0"):
        super().__init__(model_path, conf_threshold, iou_threshold, input_size, class_names)
        self.adapter_module = adapter_module or os.getenv("LINQ_ADAPTER_MODULE", "linq_adapter")
        self.output_node_name = output_node_name
        self._runtime = None
        self.is_emulated = False  # This backend never emulates hardware.
        if self.model_path is not None:
            self.load()

    def load(self, model_path: Optional[str] = None) -> None:
        path = model_path or self.model_path
        self.close()
        if not path:
            raise ValueError("Compiled LinQ TPU program path is required.")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Compiled LinQ TPU program not found: {path}")
        if not self.class_names:
            raise ValueError("LINQ_TPU requires the complete class_names mapping from the trained ONNX model.")
        try:
            adapter = importlib.import_module(self.adapter_module)
        except ImportError as exc:
            raise RuntimeError(
                f"Cannot import LinQ adapter {self.adapter_module!r}. Implement linq_adapter_template.py "
                "using the organizer's usage_example_python_api.zip and installed SDK. "
                "Hardware fallback is disabled; select ONNX_CPU or MOCK explicitly for local work."
            ) from exc
        if not callable(getattr(adapter, "load", None)):
            raise TypeError("LinQ adapter must export load(program_path) returning a callable runtime.")
        runtime = adapter.load(str(path))
        if not callable(runtime):
            closer = getattr(runtime, "close", None)
            if callable(closer):
                closer()
            raise TypeError("LinQ adapter load() must return a callable runtime.")
        self._runtime = runtime
        self.model_path = path
        self.is_loaded = True

    def preprocess(self, frame: np.ndarray):
        return letterbox(frame, self.input_size)

    def postprocess(self, raw_output: Any, meta: Dict[str, Any]) -> List[Detection]:
        return decode_yolo(raw_output, meta, self.class_names, self.conf_threshold,
                           self.iou_threshold, self.output_node_name)

    _nms_indices = staticmethod(nms_indices)

    def infer(self, frame: np.ndarray) -> InferenceResult:
        if not self.is_loaded or self._runtime is None:
            raise RuntimeError("LinQ TPU runtime is not loaded. Call load() before infer().")
        t0 = time.perf_counter()
        tensor, meta = self.preprocess(frame)
        t1 = time.perf_counter()
        raw_output = self._runtime(tensor)
        t2 = time.perf_counter()
        detections = self.postprocess(raw_output, meta)
        t3 = time.perf_counter()
        total_ms = (t3 - t0) * 1000
        return InferenceResult(detections, InferenceMetrics(
            preprocess_time_ms=(t1 - t0) * 1000, inference_time_ms=(t2 - t1) * 1000,
            postprocess_time_ms=(t3 - t2) * 1000, total_time_ms=total_ms,
            fps=1000 / total_ms if total_ms else 0.0, backend_name="LINQ_TPU",
        ), frame.shape)

    def close(self) -> None:
        runtime, self._runtime = self._runtime, None
        super().close()
        closer = getattr(runtime, "close", None)
        if callable(closer):
            closer()
