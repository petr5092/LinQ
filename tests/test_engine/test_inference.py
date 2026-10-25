"""
Расширенные тесты слоя аппаратного инференса (HAL) согласно стандарту test-master.
Покрытие: Base, BoundingBox, LocalONNXEngine, LinQTPUEngine, MockInferenceEngine, Factory.
"""

import os
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

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


# ==============================================================================
# 1. BoundingBox: граничные случаи и геометрия
# ==============================================================================

def test_bounding_box_inverted_and_normalization():
    """Проверка автоматической нормализации инвертированных координат (x2 < x1 или y2 < y1)."""
    box = BoundingBox(x1=150.0, y1=200.0, x2=50.0, y2=100.0)
    assert box.x1 == 50.0
    assert box.x2 == 150.0
    assert box.y1 == 100.0
    assert box.y2 == 200.0
    assert box.width == 100.0
    assert box.height == 100.0
    assert box.center == (100.0, 150.0)
    assert box.bottom_center == (100.0, 200.0)
    assert box.area == 10000.0


def test_bounding_box_clipping_and_formats():
    """Проверка обрезки координат пределами кадра и форматов экспорта."""
    box = BoundingBox(x1=-50.0, y1=-20.0, x2=1950.0, y2=1100.0)
    clipped = box.clip(max_width=1920, max_height=1080)

    assert clipped.x1 == 0.0
    assert clipped.y1 == 0.0
    assert clipped.x2 == 1920.0
    assert clipped.y2 == 1080.0

    # Проверка as_xyxy, as_int_xyxy, as_xywh
    assert clipped.as_xyxy() == (0.0, 0.0, 1920.0, 1080.0)
    assert clipped.as_int_xyxy() == (0, 0, 1920, 1080)
    assert clipped.as_xywh() == (0.0, 0.0, 1920.0, 1080.0)


def test_bounding_box_iou_edge_cases():
    """IoU при нулевой площади, касании граней и полном включении."""
    zero_box = BoundingBox(10.0, 10.0, 10.0, 10.0)
    other = BoundingBox(0.0, 0.0, 20.0, 20.0)
    assert zero_box.iou(other) == 0.0
    assert other.iou(zero_box) == 0.0

    # Касание по грани (inter_area = 0)
    box_a = BoundingBox(0.0, 0.0, 50.0, 50.0)
    box_b = BoundingBox(50.0, 0.0, 100.0, 50.0)
    assert box_a.iou(box_b) == 0.0


def test_inference_result_structure():
    """Проверка структуры InferenceResult и InferenceMetrics."""
    det = Detection(BoundingBox(10, 10, 50, 50), 0.9, 0, "person")
    metrics = InferenceMetrics(1.0, 10.0, 2.0, 13.0, 76.9, "MOCK")
    res = InferenceResult([det], metrics, (480, 640))
    assert len(res.detections) == 1
    assert res.metrics.fps == 76.9
    assert res.original_shape == (480, 640)


# ==============================================================================
# 2. LocalONNXEngine: Letterbox, NMS и парсинг выходных тензоров
# ==============================================================================

def test_local_onnx_letterbox_preprocessing():
    """Проверка сохранения пропорций (aspect ratio) и вычисления отступов."""
    engine = LocalONNXEngine(model_path=None, input_size=(640, 640))
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    tensor, meta = engine.preprocess(frame)

    assert tensor.shape == (1, 3, 640, 640)
    assert tensor.dtype == np.float32
    assert tensor.min() >= 0.0 and tensor.max() <= 1.0

    assert meta["orig_shape"] == (1080, 1920)
    assert meta["scale"] == pytest.approx(640 / 1920, abs=1e-4)
    assert meta["pad_x"] == 0.0
    assert meta["pad_y"] > 0.0


def test_local_onnx_postprocess_yolov8_format():
    """Парсинг транспонированного тензора YOLOv8 [1, 4 + classes, candidates]."""
    engine = LocalONNXEngine(
        model_path=None,
        conf_threshold=0.50,
        iou_threshold=0.45,
        class_names={0: "person", 1: "helmet"},
    )
    meta = {"orig_shape": (1080, 1920), "scale": 1.0, "pad_x": 0.0, "pad_y": 0.0}

    # 1. Бокс с высокой вероятностью класса 'person'
    output = np.zeros((1, 6, 2), dtype=np.float32)
    output[0, :, 0] = [100.0, 100.0, 50.0, 100.0, 0.90, 0.05]
    # 2. Бокс с низкой вероятностью (должен отфильтроваться)
    output[0, :, 1] = [200.0, 200.0, 30.0, 30.0, 0.20, 0.10]

    detections = engine.postprocess([output], meta)
    assert len(detections) == 1
    d = detections[0]
    assert d.class_name == "person"
    assert d.class_id == 0
    assert d.confidence == pytest.approx(0.90, abs=1e-3)
    assert d.bbox.x1 == 75.0
    assert d.bbox.x2 == 125.0


def test_local_onnx_nms_filtering():
    """Тестирование подавления немаксимумов (NMS) для сильно перекрывающихся рамок."""
    engine = LocalONNXEngine(model_path=None, conf_threshold=0.5, iou_threshold=0.4, class_names={0: "person"})
    meta = {"orig_shape": (640, 640), "scale": 1.0, "pad_x": 0.0, "pad_y": 0.0}

    # Два бокса одного класса на одном и том же месте с разной уверенностью
    output = np.zeros((1, 5, 2), dtype=np.float32)
    output[0, :, 0] = [100.0, 100.0, 50.0, 50.0, 0.95]
    output[0, :, 1] = [102.0, 102.0, 50.0, 50.0, 0.80]

    detections = engine.postprocess([output], meta)
    assert len(detections) == 1
    assert detections[0].confidence == pytest.approx(0.95, abs=1e-3)


def test_local_onnx_engine_full_infer_with_mock_session():
    """Сквозной тест infer() в LocalONNXEngine с моком ONNXRuntime сессии."""
    engine = LocalONNXEngine(model_path=None, class_names={0: "person"})
    mock_session = MagicMock()
    raw_tensor = np.zeros((1, 5, 1), dtype=np.float32)
    raw_tensor[0, :, 0] = [100.0, 100.0, 50.0, 100.0, 0.95]
    mock_session.run.return_value = [raw_tensor]
    mock_session.get_inputs.return_value = [MagicMock(name="input", shape=[1, 3, 640, 640])]
    mock_session.get_outputs.return_value = [MagicMock(name="output0")]
    engine.session = mock_session
    engine.is_loaded = True
    engine.input_name = "input"
    engine.output_names = ["output0"]

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    res = engine.infer(frame)
    assert len(res.detections) == 1
    assert res.detections[0].class_name == "person"
    assert res.metrics.backend_name == "ONNX_CPU"
    assert res.metrics.fps > 0.0


def test_two_stage_ppe_engine_creation_and_fusion():
    """Проверка фабрики и слияния детекций человека и СИЗ в TwoStagePPEEngine."""
    from engine.inference.two_stage import TwoStagePPEEngine

    with patch("os.path.isfile", return_value=True), \
         patch("engine.inference.two_stage.LocalONNXEngine") as mock_onnx_cls:
        # Мокируем safety engine и person engine
        mock_safety = MagicMock()
        mock_safety.is_loaded = True
        mock_safety.class_names = {0: "hardhat", 1: "safety vest"}
        mock_safety.infer.return_value = InferenceResult(
            detections=[Detection(BoundingBox(10, 10, 50, 50), 0.9, 0, "hardhat")],
            metrics=InferenceMetrics(backend_name="ONNX_CPU", preprocess_time_ms=2.0, postprocess_time_ms=1.0),
        )

        mock_person = MagicMock()
        mock_person.is_loaded = True
        mock_person.class_names = {0: "person"}
        mock_person.infer.return_value = InferenceResult(
            detections=[Detection(BoundingBox(0, 0, 100, 200), 0.95, 0, "person")],
            metrics=InferenceMetrics(backend_name="ONNX_CPU"),
        )

        mock_onnx_cls.side_effect = [mock_safety, mock_person]

        engine = create_inference_engine(backend="TWO_STAGE")
        assert isinstance(engine, TwoStagePPEEngine)
        assert engine.backend_name == "TWO_STAGE_PPE"

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = engine.infer(frame)

        assert len(result.detections) == 2
        classes = {d.class_name for d in result.detections}
        assert "person" in classes
        assert "hardhat" in classes
        assert result.metrics.backend_name == "TWO_STAGE_PPE"

