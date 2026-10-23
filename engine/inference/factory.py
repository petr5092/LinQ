"""
Фабрика инференс-движков HAL.
Позволяет бесшовно переключаться между LinQ TPU, локальным ONNX CPU и Mock через переменную окружения INFERENCE_BACKEND.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from engine.inference.base import BaseInferenceEngine
from engine.inference.local_onnx import LocalONNXEngine
from engine.inference.linq_tpu import LinQTPUEngine
from engine.inference.mock import MockInferenceEngine


def create_inference_engine(
    backend: Optional[str] = None,
    model_path: Optional[str] = None,
    conf_threshold: float = 0.35,
    iou_threshold: float = 0.45,
    input_size: Tuple[int, int] = (640, 640),
    class_names: Optional[Dict[int, str]] = None,
    **kwargs: Any,
) -> BaseInferenceEngine:
    """
    Создает инференс-движок на основе настроек.

    :param backend: "LINQ_TPU", "ONNX_CPU" или "MOCK". По умолчанию берется из env INFERENCE_BACKEND.
    :param model_path: Путь к файлу модели (.tpu или .onnx).
    """
    chosen_backend = (backend or os.getenv("INFERENCE_BACKEND", "ONNX_CPU")).upper().strip()

    if chosen_backend == "LINQ_TPU":
        target_path = model_path or os.getenv("TPU_MODEL_PATH", "models/tpu/safety_yolov8_h1m.tpu")
        return LinQTPUEngine(
            model_path=target_path,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            input_size=input_size,
            class_names=class_names,
            **kwargs,
        )

    elif chosen_backend == "MOCK":
        return MockInferenceEngine(
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            input_size=input_size,
            class_names=class_names,
            **kwargs,
        )

    else:  # По умолчанию ONNX_CPU
        target_path = model_path or os.getenv("ONNX_MODEL_PATH", "models/onnx/safety_yolov8.onnx")
        # Если файл не существует, предупреждаем и используем мок или фоллбэк
        if not os.path.exists(target_path):
            print(f"[InferenceFactory] Модель {target_path} не найдена. Создается MockInferenceEngine.")
            return MockInferenceEngine(
                conf_threshold=conf_threshold,
                iou_threshold=iou_threshold,
                input_size=input_size,
                class_names=class_names,
                **kwargs,
            )

        return LocalONNXEngine(
            model_path=target_path,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            input_size=input_size,
            class_names=class_names,
            **kwargs,
        )
