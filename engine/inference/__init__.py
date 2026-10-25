"""
Пакет слоя аппаратного инференса (HAL) LinQ Safety Guard.
"""

from engine.inference.base import (
    BaseInferenceEngine,
    BoundingBox,
    Detection,
    InferenceMetrics,
    InferenceResult,
)
from engine.inference.factory import create_inference_engine
from engine.inference.linq_tpu import LinQTPUEngine
from engine.inference.local_onnx import LocalONNXEngine
from engine.inference.mock import MockInferenceEngine
from engine.inference.two_stage import TwoStagePPEEngine

__all__ = [
    "BaseInferenceEngine",
    "BoundingBox",
    "Detection",
    "InferenceMetrics",
    "InferenceResult",
    "create_inference_engine",
    "LinQTPUEngine",
    "LocalONNXEngine",
    "MockInferenceEngine",
    "TwoStagePPEEngine",
]
