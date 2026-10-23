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
    engine = LocalONNXEngine(model_path=None, conf_threshold=0.5, iou_threshold=0.4)
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


# ==============================================================================
# 3. LinQTPUEngine: Аппаратный HAL и эмуляция
# ==============================================================================

def test_linq_tpu_engine_initialization_and_infer():
    """Инициализация LinQ TPU в режиме эмуляции, инференс и закрытие."""
    unloaded = LinQTPUEngine(model_path=None)
    with pytest.raises(ValueError):
        unloaded.load(None)

    tpu_engine = LinQTPUEngine(
        model_path="models/tpu/sample.tpu",
        conf_threshold=0.5,
        class_names={0: "person", 1: "vest"},
    )
    assert tpu_engine.is_loaded is True
    assert tpu_engine.is_emulated is True

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    res = tpu_engine.infer(frame)
    assert isinstance(res, InferenceResult)
    assert res.metrics.backend_name == "LinQ_TPU_H1M_Emulated"
    assert res.metrics.total_time_ms > 0

    tpu_engine.close()
    assert tpu_engine.is_loaded is False

    # Повторный infer после close вызывает исключение
    with pytest.raises(RuntimeError):
        tpu_engine.infer(frame)


def test_linq_tpu_nms_vectorized():
    """Проверка векторного NMS внутри LinQTPUEngine для перекрывающихся рамок."""
    boxes = np.array([
        [10.0, 10.0, 50.0, 50.0],
        [12.0, 12.0, 50.0, 50.0],
        [100.0, 100.0, 150.0, 150.0],
    ], dtype=np.float32)
    scores = np.array([0.9, 0.8, 0.95], dtype=np.float32)

    keep = LinQTPUEngine._nms_indices(
        boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3], scores, iou_thresh=0.45
    )
    assert len(keep) == 2
    assert 2 in keep  # третий бокс (score 0.95)
    assert 0 in keep  # первый бокс (score 0.9)


def test_linq_tpu_hardware_mock():
    """Тестирование инициализации реального оборудования LinQ TPU через мок pytpu."""
    mock_tpu_module = MagicMock()
    mock_tpu_module.Device.list_devices.return_value = ["/dev/tpu0"]
    mock_dev = MagicMock()
    mock_prog = MagicMock()
    mock_sess = MagicMock()
    mock_sess.run.return_value = np.zeros((1, 5, 1), dtype=np.float32)

    mock_tpu_module.Device.open.return_value = mock_dev
    mock_dev.load.return_value = mock_prog
    mock_prog.inference.return_value = mock_sess

    with patch("engine.inference.linq_tpu.HAS_PYTPU", True), \
         patch("engine.inference.linq_tpu.tpu", mock_tpu_module):

        engine = LinQTPUEngine(model_path="safety.tpu")
        assert engine.is_emulated is False
        assert engine.is_loaded is True

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        res = engine.infer(frame)
        assert res.metrics.backend_name == "LinQ_TPU_H1M"
        assert mock_sess.run.called

        engine.close()
        assert mock_sess.close.called
        assert mock_dev.close.called


def test_linq_tpu_engine_context_manager():
    """Контекстный менеджер HAL-движка TPU."""
    with LinQTPUEngine(model_path="models/tpu/sample.tpu") as engine:
        assert engine.is_loaded is True
    assert engine.is_loaded is False


# ==============================================================================
# 4. MockInferenceEngine & Factory
# ==============================================================================

def test_mock_engine_dynamic_canned_updates():
    """Динамическое переключение детекций в моке для синтетических тестов."""
    engine = MockInferenceEngine()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # По умолчанию детекций нет
    res1 = engine.infer(frame)
    assert len(res1.detections) == 0

    # Устанавливаем последовательность
    det = Detection(BoundingBox(10, 10, 50, 50), 0.9, 0, "person")
    engine.set_canned_detections([[det]])
    res2 = engine.infer(frame)
    assert len(res2.detections) == 1


def test_inference_factory_branches(monkeypatch, tmp_path):
    """Фабрика: ветки TPU, Mock и ONNX_CPU."""
    # 1. LINQ_TPU
    e_tpu = create_inference_engine(backend="LINQ_TPU", model_path="model.tpu")
    assert isinstance(e_tpu, LinQTPUEngine)
    e_tpu.close()

    # 2. MOCK
    e_mock = create_inference_engine(backend="MOCK")
    assert isinstance(e_mock, MockInferenceEngine)

    # 3. ONNX_CPU с отсутствующим файлом -> Mock
    monkeypatch.setenv("INFERENCE_BACKEND", "ONNX_CPU")
    monkeypatch.setenv("ONNX_MODEL_PATH", "missing.onnx")
    e_fb = create_inference_engine()
    assert isinstance(e_fb, MockInferenceEngine)

    # 4. ONNX_CPU с существующим файлом
    dummy_onnx = tmp_path / "model.onnx"
    dummy_onnx.write_bytes(b"dummy")
    with patch("onnxruntime.InferenceSession"):
        e_onnx = create_inference_engine(backend="ONNX_CPU", model_path=str(dummy_onnx))
        assert isinstance(e_onnx, LocalONNXEngine)
