"""
Two-Stage ROI / Cascade Inference Engine.
Stage 1: High-accuracy person localization (COCO YOLOv8n / ByteTrack).
Stage 2: Specialised PPE and safety compliance analysis (hardhat, safety vest, machinery).
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from engine.inference.base import (
    BaseInferenceEngine,
    Detection,
    InferenceMetrics,
    InferenceResult,
)
from engine.inference.local_onnx import LocalONNXEngine


class TwoStagePPEEngine(BaseInferenceEngine):
    """
    Двухстадийный каскадный инференс:
    1-я стадия: Высокоточное обнаружение силуэтов людей (person).
    2-я стадия: Специализированная детекция СИЗ (каски, жилеты, техника, опасные зоны).
    """

    def __init__(
        self,
        safety_model_path: Optional[str] = None,
        person_model_path: Optional[str] = None,
        conf_threshold: float = 0.20,
        person_conf_threshold: float = 0.35,
        iou_threshold: float = 0.45,
        input_size: Tuple[int, int] = (640, 640),
        class_names: Optional[Dict[int, str]] = None,
        **kwargs: Any,
    ) -> None:
        proj_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.safety_model_path = safety_model_path or os.getenv(
            "ONNX_MODEL_PATH",
            os.path.join(proj_root, "models", "onnx", "safety_yolov8.onnx"),
        )
        self.person_model_path = person_model_path or os.getenv(
            "PERSON_MODEL_PATH",
            os.path.join(proj_root, "models", "onnx", "person_yolov8n.onnx"),
        )
        self.person_conf_threshold = person_conf_threshold

        super().__init__(
            model_path=self.safety_model_path,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            input_size=input_size,
            class_names=class_names,
        )

        self.safety_engine: Optional[LocalONNXEngine] = None
        self.person_engine: Optional[LocalONNXEngine] = None
        self.backend_name = "TWO_STAGE_PPE"

        self.load()

    def load(self, model_path: Optional[str] = None) -> None:
        safety_path = model_path or self.safety_model_path
        if not safety_path or not os.path.isfile(safety_path):
            raise FileNotFoundError(f"Safety model not found: {safety_path}")

        self.safety_engine = LocalONNXEngine(
            model_path=safety_path,
            conf_threshold=self.conf_threshold,
            iou_threshold=self.iou_threshold,
            input_size=self.input_size,
        )
        self.class_names = self.safety_engine.class_names.copy()

        # Попытка подключить специализированный детектор людей 1-й стадии
        if self.person_model_path and os.path.isfile(self.person_model_path):
            try:
                self.person_engine = LocalONNXEngine(
                    model_path=self.person_model_path,
                    conf_threshold=self.person_conf_threshold,
                    iou_threshold=self.iou_threshold,
                    input_size=self.input_size,
                )
            except Exception:
                self.person_engine = None

        self.is_loaded = self.safety_engine.is_loaded

    def preprocess(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        if self.safety_engine:
            return self.safety_engine.preprocess(frame)
        raise RuntimeError("Safety engine is not loaded.")

    def postprocess(self, raw_output: Any, meta: Dict[str, Any]) -> List[Detection]:
        if self.safety_engine:
            return self.safety_engine.postprocess(raw_output, meta)
        return []

    def infer(self, frame: np.ndarray) -> InferenceResult:
        if not self.is_loaded or self.safety_engine is None:
            raise RuntimeError("TwoStagePPEEngine is not loaded.")

        t0 = time.perf_counter()

        # 1. Запуск детектора СИЗ и атрибутов безопасности
        safety_res = self.safety_engine.infer(frame)
        safety_dets = safety_res.detections

        # 2. Запуск детектора человека (1-я стадия) при наличии
        person_dets: List[Detection] = []
        if self.person_engine is not None:
            try:
                person_res = self.person_engine.infer(frame)
                person_dets = [d for d in person_res.detections if d.class_name == "person"]
            except Exception:
                person_dets = []

        # Объединение результатов:
        # Если детектор людей отработал, берем проверенных людей из него,
        # а СИЗ (каски, жилеты, техника, опасные зоны) — из специализированной модели.
        if person_dets:
            final_dets = person_dets + [d for d in safety_dets if d.class_name != "person"]
        else:
            final_dets = safety_dets

        t_end = time.perf_counter()
        total_ms = (t_end - t0) * 1000.0

        metrics = InferenceMetrics(
            preprocess_time_ms=safety_res.metrics.preprocess_time_ms,
            inference_time_ms=total_ms - safety_res.metrics.preprocess_time_ms - safety_res.metrics.postprocess_time_ms,
            postprocess_time_ms=safety_res.metrics.postprocess_time_ms,
            total_time_ms=total_ms,
            fps=1000.0 / total_ms if total_ms > 0 else 0.0,
            backend_name=self.backend_name,
        )

        return InferenceResult(final_dets, metrics, frame.shape)

    def close(self) -> None:
        if self.safety_engine:
            self.safety_engine.close()
        if self.person_engine:
            self.person_engine.close()
        super().close()
