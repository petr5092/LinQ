"""
Ядро компьютерного зрения (CV Engine) LinQ Safety Guard.
Включает слои:
- inference: аппаратный инференс LinQ TPU (H1M) / ONNX CPU / Mock
- tracking: пространственно-временной трекинг объектов (ByteTrack)
- rules: движок правил ТБ (опасные зоны, сближение, падения, СИЗ)
- deduplication: анти-спам и подавление ложных тревог (debounce & cooldown)
- pipeline: сквозной координатор CVPipeline
"""

from engine.deduplication.anti_spam import AntiSpamEngine
from engine.deduplication.types import ConfirmedIncident, IncidentState
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
from engine.pipeline import CVPipeline, FrameProcessingResult, PipelineMetrics
from engine.rules.base import BaseRule, FrameContext, RuleViolation, ViolationSeverity
from engine.rules.danger_zone import DangerZoneRule, ZoneDefinition
from engine.rules.engine import RulesEngine
from engine.rules.fall_detection import FallDetectionRule
from engine.rules.ppe_compliance import PPEComplianceRule
from engine.rules.proximity import ProximityRule
from engine.tracking.kalman import KalmanBoxTracker
from engine.tracking.tracker import ByteTracker
from engine.tracking.types import TrackState, TrackedObject

__all__ = [
    # Pipeline
    "CVPipeline",
    "FrameProcessingResult",
    "PipelineMetrics",
    # Inference HAL
    "BaseInferenceEngine",
    "BoundingBox",
    "Detection",
    "InferenceMetrics",
    "InferenceResult",
    "create_inference_engine",
    "LinQTPUEngine",
    "LocalONNXEngine",
    "MockInferenceEngine",
    # Tracking
    "KalmanBoxTracker",
    "ByteTracker",
    "TrackState",
    "TrackedObject",
    # Rules
    "BaseRule",
    "FrameContext",
    "RuleViolation",
    "ViolationSeverity",
    "DangerZoneRule",
    "ZoneDefinition",
    "RulesEngine",
    "FallDetectionRule",
    "PPEComplianceRule",
    "ProximityRule",
    # Deduplication
    "AntiSpamEngine",
    "ConfirmedIncident",
    "IncidentState",
]
