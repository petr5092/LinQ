"""
Тесты загрузки, валидации формы тензоров и инференса новой модели YOLOv8n PPE.
"""

import json
import os
from pathlib import Path
import numpy as np
import pytest

from engine.inference.factory import create_inference_engine
from engine.inference.local_onnx import LocalONNXEngine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "onnx" / "safety_yolov8.onnx"
CLASSES_PATH = PROJECT_ROOT / "models" / "onnx" / "safety_yolov8n_classes.json"


def test_model_files_exist():
    assert MODEL_PATH.exists(), f"Модель не найдена: {MODEL_PATH}"
    assert MODEL_PATH.stat().st_size > 1_000_000, "Размер ONNX-модели подозрительно мал"
    assert CLASSES_PATH.exists(), f"Файл классов не найден: {CLASSES_PATH}"


def test_classes_mapping_contains_safety_categories():
    with open(CLASSES_PATH, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    class_names = set(mapping.values())
    assert "person" in class_names, "Класс 'person' отсутствует в маппинге модели"
    assert any(c in class_names for c in ("helmet", "hardhat")), "Класс каски ('helmet'/'hardhat') отсутствует"
    assert any(c in class_names for c in ("no_helmet", "no-hardhat")), "Класс отсутствия каски отсутствует"
    assert any(c in class_names for c in ("vest", "safety vest")), "Класс жилета ('vest'/'safety vest') отсутствует"
    assert any(c in class_names for c in ("no_vest", "no-safety vest")), "Класс отсутствия жилета отсутствует"


def test_local_onnx_engine_inference_with_safety_model():
    with open(CLASSES_PATH, "r", encoding="utf-8") as f:
        raw_map = json.load(f)
    int_map = {int(k): v for k, v in raw_map.items()}

    engine = LocalONNXEngine(
        model_path=str(MODEL_PATH),
        conf_threshold=0.25,
        iou_threshold=0.45,
        class_names=int_map,
    )

    assert engine.session is not None
    assert engine.input_name == "images"
    assert "output0" in engine.output_names

    # Синтетический тестовый кадр (FullHD)
    dummy_frame = np.random.randint(0, 256, (720, 1280, 3), dtype=np.uint8)
    result = engine.infer(dummy_frame)

    assert result is not None
    assert result.original_shape == (720, 1280, 3)
    assert result.metrics.total_time_ms > 0.0
    assert result.metrics.fps > 0.0
    assert isinstance(result.detections, list)


def test_inference_factory_resolves_safety_model():
    engine = create_inference_engine(
        backend="ONNX_CPU",
        model_path=str(MODEL_PATH),
    )
    assert isinstance(engine, LocalONNXEngine)
    assert engine.model_path == str(MODEL_PATH)
