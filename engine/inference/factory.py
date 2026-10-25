"""Factory for creating inference engine instances."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from engine.inference.base import BaseInferenceEngine
from engine.inference.linq_tpu import LinQTPUEngine
from engine.inference.local_onnx import LocalONNXEngine
from engine.inference.mock import MockInferenceEngine
from engine.inference.two_stage import TwoStagePPEEngine
from engine.inference.linq_fast_bridge import LinQFastBridgeEngine


def create_inference_engine(backend: Optional[str] = None, model_path: Optional[str] = None,
                            conf_threshold: float = 0.35, iou_threshold: float = 0.45,
                            input_size: Tuple[int, int] = (640, 640),
                            class_names: Optional[Dict[int, str]] = None,
                            **kwargs: Any) -> BaseInferenceEngine:
    raw_backend = (backend if backend is not None else os.getenv("INFERENCE_BACKEND", "ONNX_CPU")).upper().strip()
    aliases = {
        "LINQ": "LINQ_TPU",
        "ONNX": "ONNX_CPU",
        "LINQ_REMOTE": "LINQ_REMOTE",
        "REMOTE": "LINQ_REMOTE",
        "CASCADE": "TWO_STAGE",
        "TWO_STAGE_PPE": "TWO_STAGE",
        "FAST_BRIDGE": "LINQ_FAST_BRIDGE",
        "BRIDGE": "LINQ_FAST_BRIDGE",
        "LINQ_BRIDGE": "LINQ_FAST_BRIDGE",
    }
    chosen_backend = aliases.get(raw_backend, raw_backend)
    options = dict(conf_threshold=conf_threshold, iou_threshold=iou_threshold,
                   input_size=input_size, class_names=class_names, **kwargs)
    if chosen_backend == "MOCK":
        return MockInferenceEngine(**options)
    if chosen_backend == "TWO_STAGE":
        return TwoStagePPEEngine(safety_model_path=model_path, **options)
    if chosen_backend == "LINQ_FAST_BRIDGE":
        return LinQFastBridgeEngine(**options)
    if chosen_backend in ("LINQ_TPU", "LINQ_REMOTE"):
        proj_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        default_tpu = os.path.join(proj_root, "models", "tpu", "safety_yolov8n_b1_o1_h1m.tpu")
        if not os.path.isfile(default_tpu):
            default_tpu = "models/tpu/safety_yolov8n_b1_o1_h1m.tpu"
        env_tpu = os.getenv("TPU_MODEL_PATH")
        if model_path:
            path = model_path
        elif env_tpu and os.path.isfile(env_tpu):
            path = env_tpu
        elif env_tpu and os.path.isfile(os.path.join(proj_root, env_tpu)):
            path = os.path.join(proj_root, env_tpu)
        else:
            path = default_tpu
        engine = LinQTPUEngine(model_path=path, **options)
    elif chosen_backend == "ONNX_CPU":
        path = model_path or os.getenv("ONNX_MODEL_PATH", "models/onnx/safety_yolov8.onnx")
        engine = LocalONNXEngine(model_path=path, **options)
    else:
        raise ValueError(f"Unknown inference backend {chosen_backend!r}; choose ONNX_CPU, LINQ_TPU or MOCK.")
    if not engine.is_loaded:
        raise RuntimeError(f"{chosen_backend} did not load its model.")
    return engine
