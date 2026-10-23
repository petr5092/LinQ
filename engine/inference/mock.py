"""
Mock Inference Engine — Детерминированный генератор детекций для быстрого тестирования.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from engine.inference.base import (
    BaseInferenceEngine,
    BoundingBox,
    Detection,
    InferenceMetrics,
    InferenceResult,
)


class MockInferenceEngine(BaseInferenceEngine):
    """
    Мок-движок для изолированного тестирования трекинга, правил и пайплайна.
    """

    def __init__(
        self,
        canned_detections: Optional[List[List[Detection]]] = None,
        conf_threshold: float = 0.35,
        iou_threshold: float = 0.45,
        input_size: Tuple[int, int] = (640, 640),
        class_names: Optional[Dict[int, str]] = None,
        simulated_delay_ms: float = 1.0,
    ) -> None:
        super().__init__(
            model_path="mock://model",
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            input_size=input_size,
            class_names=class_names,
        )
        self.canned_detections = canned_detections or []
        self.frame_idx = 0
        self.simulated_delay_ms = simulated_delay_ms
        self.is_loaded = True

    def set_canned_detections(self, detections_per_frame: List[List[Detection]]) -> None:
        self.canned_detections = detections_per_frame
        self.frame_idx = 0

    def load(self, model_path: Optional[str] = None) -> None:
        self.is_loaded = True

    def preprocess(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        orig_h, orig_w = frame.shape[:2]
        return np.zeros((1, 3, self.input_size[1], self.input_size[0]), dtype=np.float32), {
            "orig_shape": (orig_h, orig_w),
            "scale": 1.0,
            "pad_x": 0.0,
            "pad_y": 0.0,
        }

    def postprocess(self, raw_output: Any, meta: Dict[str, Any]) -> List[Detection]:
        if not self.canned_detections:
            return []
        idx = self.frame_idx % len(self.canned_detections)
        return self.canned_detections[idx]

    def infer(self, frame: np.ndarray) -> InferenceResult:
        t0 = time.perf_counter()
        if self.simulated_delay_ms > 0:
            time.sleep(self.simulated_delay_ms / 1000.0)

        dets = self.postprocess(None, {"orig_shape": frame.shape[:2]})
        self.frame_idx += 1
        t1 = time.perf_counter()

        tot_ms = (t1 - t0) * 1000.0
        fps = 1000.0 / tot_ms if tot_ms > 0 else 100.0

        return InferenceResult(
            detections=dets,
            metrics=InferenceMetrics(
                preprocess_time_ms=0.1,
                inference_time_ms=round(tot_ms, 2),
                postprocess_time_ms=0.1,
                total_time_ms=round(tot_ms + 0.2, 2),
                fps=round(fps, 1),
                backend_name="MOCK_ENGINE",
            ),
            original_shape=frame.shape,
        )
