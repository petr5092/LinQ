"""
Тесты слоя абстракции аппаратного инференса (HAL).
"""

import numpy as np
import pytest

from engine.inference.base import BoundingBox, Detection, InferenceMetrics, InferenceResult
from engine.inference.factory import create_inference_engine
from engine.inference.linq_tpu import LinQTPUEngine
from engine.inference.mock import MockInferenceEngine


def test_bounding_box_geometry():
    box = BoundingBox(x1=10.0, y1=20.0, x2=110.0, y2=220.0)

    assert box.width == 100.0
    assert box.height == 200.0
    assert box.area == 20000.0
    assert box.center == (60.0, 120.0)
    assert box.bottom_center == (60.0, 220.0)
    assert box.aspect_ratio == pytest.approx(0.5, 0.01)

    # IoU с идентичной рамкой = 1.0
    assert box.iou(box) == pytest.approx(1.0, 0.001)

    # IoU с непересекающейся рамкой = 0.0
    outside_box = BoundingBox(x1=300.0, y1=300.0, x2=400.0, y2=400.0)
    assert box.iou(outside_box) == 0.0

    # IoU с частичным перекрытием (50x100 перекрытие)
    overlap_box = BoundingBox(x1=60.0, y1=20.0, x2=160.0, y2=220.0)
    # inter = 50 * 200 = 10000; union = 20000 + 20000 - 10000 = 30000 -> 1/3
    assert box.iou(overlap_box) == pytest.approx(1.0 / 3.0, 0.01)


def test_bounding_box_sub_regions():
    box = BoundingBox(x1=0.0, y1=0.0, x2=60.0, y2=180.0)
    head = box.head_box
    torso = box.torso_box

    assert head.y1 == 0.0
    assert head.y2 == pytest.approx(59.4, 0.1)
    assert torso.y1 > head.y1


def test_mock_inference_engine():
    mock_box = BoundingBox(10.0, 10.0, 50.0, 100.0)
    mock_det = Detection(bbox=mock_box, confidence=0.92, class_id=0, class_name="person")

    engine = MockInferenceEngine(canned_detections=[[mock_det]])
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    result = engine.infer(frame)
    assert len(result.detections) == 1
    assert result.detections[0].class_name == "person"
    assert result.detections[0].confidence == 0.92
    assert result.metrics.fps > 0.0
    assert result.metrics.backend_name == "MOCK_ENGINE"


def test_linq_tpu_engine_emulated():
    engine = LinQTPUEngine(model_path="models/tpu/safety_yolov8_h1m.tpu")
    assert engine.is_loaded is True

    frame = np.zeros((640, 640, 3), dtype=np.uint8)
    tensor, meta = engine.preprocess(frame)

    assert tensor.shape == (1, 3, 640, 640)
    assert tensor.dtype == np.float32

    result = engine.infer(frame)
    assert isinstance(result, InferenceResult)
    assert "LinQ_TPU" in result.metrics.backend_name
    assert result.metrics.inference_time_ms > 0.0
    engine.close()


def test_inference_factory(monkeypatch):
    monkeypatch.setenv("INFERENCE_BACKEND", "MOCK")
    engine = create_inference_engine()
    assert isinstance(engine, MockInferenceEngine)

    monkeypatch.setenv("INFERENCE_BACKEND", "LINQ_TPU")
    tpu_engine = create_inference_engine()
    assert isinstance(tpu_engine, LinQTPUEngine)
