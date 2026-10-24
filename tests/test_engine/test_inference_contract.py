"""Regression checks for strict backends, trained labels and shared YOLO geometry."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from engine.inference.base import BoundingBox, Detection
from engine.inference.factory import create_inference_engine
from engine.inference.linq_tpu import LinQTPUEngine
from engine.inference.local_onnx import LocalONNXEngine
from engine.inference.mock import MockInferenceEngine


META = {"orig_shape": (640, 640), "scale": 1.0, "pad_x": 0, "pad_y": 0}


def make_session(names=None, input_shape=None, output_shape=None):
    session = MagicMock()
    session.get_inputs.return_value = [SimpleNamespace(name="images", type="tensor(float)",
        shape=input_shape if input_shape is not None else [1, 3, 640, 640])]
    session.get_outputs.return_value = [SimpleNamespace(name="output0", shape=output_shape or [1, 6, 8400])]
    session.get_modelmeta.return_value = SimpleNamespace(custom_metadata_map={
        "names": repr(names if names is not None else {0: "person", 1: "helmet"}), "task": "detect",
    })
    return session


@pytest.fixture
def model_file(tmp_path):
    path = tmp_path / "model.onnx"
    path.write_bytes(b"placeholder: model execution is mocked in these unit tests")
    return str(path)


def test_factory_only_uses_mock_when_explicit(monkeypatch, tmp_path):
    monkeypatch.setenv("INFERENCE_BACKEND", "ONNX_CPU")
    monkeypatch.setenv("ONNX_MODEL_PATH", str(tmp_path / "missing.onnx"))
    with pytest.raises(FileNotFoundError):
        create_inference_engine()
    with pytest.raises(ValueError, match="Unknown inference backend"):
        create_inference_engine(backend="ONNX_CUP")
    assert isinstance(create_inference_engine(backend="MOCK"), MockInferenceEngine)


@pytest.mark.parametrize("engine_type", [LocalONNXEngine, LinQTPUEngine])
def test_explicit_missing_model_fails_at_construction(engine_type, tmp_path):
    with pytest.raises(FileNotFoundError):
        engine_type(model_path=str(tmp_path / "missing.model"))


def test_onnx_loads_model_metadata_without_guessing_labels(model_file):
    names = {i: f"coco_{i}" for i in range(80)}
    names.update({0: "person", 1: "bicycle", 2: "car"})
    session = make_session(names=names, output_shape=[1, 84, 8400])
    raw = np.zeros((1, 84, 8400), dtype=np.float32)
    raw[0, :4, 0] = [320, 320, 100, 200]
    raw[0, 5, 0] = 0.95
    session.run.return_value = [raw]
    with patch("engine.inference.local_onnx.ort.InferenceSession", return_value=session):
        engine = create_inference_engine(backend="ONNX_CPU", model_path=model_file)
    result = engine.infer(np.zeros((640, 640, 3), dtype=np.uint8))
    assert len(result.detections) == 1
    assert result.detections[0].class_name == "bicycle"  # Never a made-up forklift label.
    assert result.detections[0].bbox.as_xyxy() == (270, 220, 370, 420)
    assert result.metrics.backend_name == "ONNX_CPU"
    engine.close()
    assert engine.session is None
    with pytest.raises(RuntimeError, match="not loaded"):
        engine.infer(np.zeros((640, 640, 3), dtype=np.uint8))


def test_onnx_rejects_conflicting_labels(model_file):
    with patch("engine.inference.local_onnx.ort.InferenceSession", return_value=make_session()):
        with pytest.raises(ValueError, match="disagree"):
            LocalONNXEngine(model_file, class_names={0: "person", 1: "forklift"})


def test_onnx_requires_explicit_labels_when_metadata_absent(model_file):
    session = make_session()
    session.get_modelmeta.return_value.custom_metadata_map = {}
    with patch("engine.inference.local_onnx.ort.InferenceSession", return_value=session):
        with pytest.raises(ValueError, match="no class names"):
            LocalONNXEngine(model_file)
        engine = LocalONNXEngine(model_file, class_names={0: "person", 1: "helmet"})
    assert engine.is_loaded


@pytest.mark.parametrize("shape", [["batch", 3, 640, 640], [1, 3, "height", "width"], [1, 640, 640, 3], [2, 3, 640, 640]])
def test_onnx_rejects_non_static_nchw_input(model_file, shape):
    with patch("engine.inference.local_onnx.ort.InferenceSession", return_value=make_session(input_shape=shape)):
        with pytest.raises(ValueError, match="static float32"):
            LocalONNXEngine(model_file)


def test_onnx_rejects_output_class_count_mismatch(model_file):
    with patch("engine.inference.local_onnx.ort.InferenceSession", return_value=make_session(output_shape=[1, 84, 8400])):
        with pytest.raises(ValueError, match="does not match"):
            LocalONNXEngine(model_file)


@pytest.mark.parametrize("class_names", [{}, {1: "person"}, {0: ""}, {0.1: "person"}])
def test_class_names_must_cover_model_classes(class_names):
    with pytest.raises(ValueError):
        LocalONNXEngine(class_names=class_names)


@pytest.mark.parametrize("engine_type", [LocalONNXEngine, LinQTPUEngine])
@pytest.mark.parametrize("frame_shape", [(301, 503), (503, 301), (1080, 1920)])
def test_letterbox_roundtrip_non_square_frame_and_input(engine_type, frame_shape):
    engine = engine_type(input_size=(640, 384), class_names={0: "person"})
    frame = np.zeros((*frame_shape, 3), dtype=np.uint8)
    frame[:, :, 2] = 255  # BGR red must become RGB red.
    tensor, meta = engine.preprocess(frame)
    assert tensor.shape == (1, 3, 384, 640)
    assert tensor.dtype == np.float32 and tensor.flags.c_contiguous
    assert tensor[0, 0, meta["pad_y"], meta["pad_x"]] == 1
    assert tensor[0, 2, meta["pad_y"], meta["pad_x"]] == 0
    h, w = frame_shape
    expected = np.array([w * 0.1, h * 0.2, w * 0.8, h * 0.9])
    x1, y1, x2, y2 = expected
    raw = np.array([[[((x1 + x2) / 2) * meta["scale_x"] + meta["pad_x"]],
                     [((y1 + y2) / 2) * meta["scale_y"] + meta["pad_y"]],
                     [(x2 - x1) * meta["scale_x"]], [(y2 - y1) * meta["scale_y"]], [0.9]]], dtype=np.float32)
    detections = engine.postprocess(raw, meta)
    assert len(detections) == 1
    np.testing.assert_allclose(detections[0].bbox.as_xyxy(), expected, atol=0.001)


@pytest.mark.parametrize("transpose", [False, True])
def test_both_output_layouts_preserve_classes_and_apply_classwise_nms(transpose):
    engine = LocalONNXEngine(class_names={0: "person", 1: "helmet"})
    rows = np.array([[100, 100, 50, 50, 0.95, 0.01],
                     [101, 101, 50, 50, 0.8, 0.01],
                     [100, 100, 50, 50, 0.01, 0.9]], dtype=np.float32)
    output = (rows.T if transpose else rows)[None]
    detections = engine.postprocess([output], META)
    assert [d.class_name for d in detections] == ["person", "helmet"]


@pytest.mark.parametrize("shape", [(2, 6, 100), (1, 7, 100), (1, 6, 6)])
def test_unsupported_or_ambiguous_outputs_fail_clearly(shape):
    engine = LocalONNXEngine(class_names={0: "person", 1: "helmet"})
    with pytest.raises(ValueError, match="shape"):
        engine.postprocess(np.zeros(shape, dtype=np.float32), META)


def test_nonfinite_degenerate_and_offscreen_boxes_do_not_create_alerts():
    engine = LocalONNXEngine(class_names={0: "person"})
    raw = np.array([[100, 100, -2, 4, 0.9], [100, 100, 2, 4, np.nan],
                    [-100, -100, 10, 10, 0.9], [100, 100, 10, 10, 0.9]], dtype=np.float32)
    assert len(engine.postprocess(raw[None], META)) == 1


def test_tpu_missing_adapter_is_not_emulated(model_file):
    engine = LinQTPUEngine(class_names={0: "person"}, adapter_module="unconfigured_linq_adapter")
    with pytest.raises(RuntimeError, match="Cannot import LinQ adapter"):
        engine.load(model_file)
    assert not engine.is_loaded and not engine.is_emulated


def test_tpu_adapter_load_errors_propagate(model_file):
    adapter = SimpleNamespace(load=MagicMock(side_effect=RuntimeError("physical device unavailable")))
    with patch("engine.inference.linq_tpu.importlib.import_module", return_value=adapter):
        engine = LinQTPUEngine(class_names={0: "person"})
        with pytest.raises(RuntimeError, match="physical device unavailable"):
            engine.load(model_file)
        assert not engine.is_loaded


def test_tpu_callable_adapter_inference_and_cleanup(model_file):
    runtime = MagicMock(return_value=np.array([[[320], [320], [100], [100], [0.95]]], dtype=np.float32))
    adapter = SimpleNamespace(load=MagicMock(return_value=runtime))
    with patch("engine.inference.linq_tpu.importlib.import_module", return_value=adapter):
        with create_inference_engine(backend="LINQ_TPU", model_path=model_file,
                                     class_names={0: "person"}) as engine:
            assert engine.is_loaded and not engine.is_emulated
            result = engine.infer(np.zeros((640, 640, 3), dtype=np.uint8))
            assert result.metrics.backend_name == "LINQ_TPU"
            assert len(result.detections) == 1
            tensor = runtime.call_args.args[0]
            assert tensor.shape == (1, 3, 640, 640) and tensor.flags.c_contiguous
    runtime.close.assert_called_once()
    assert not engine.is_loaded


def test_template_fails_at_load_time(model_file):
    with pytest.raises(NotImplementedError, match="official Python API"):
        LinQTPUEngine(model_path=model_file, class_names={0: "person"}, adapter_module="linq_adapter_template")


def test_mock_dynamic_canned_detections():
    engine = MockInferenceEngine(simulated_delay_ms=0)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert engine.infer(frame).detections == []
    detection = Detection(BoundingBox(10, 10, 50, 50), 0.9, 0, "person")
    engine.set_canned_detections([[detection]])
    assert engine.infer(frame).detections == [detection]
