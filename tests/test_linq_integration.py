"""
Тестирование интеграции с аппаратным ускорителем LinQ TPU (H1M) и слоем HAL.
Проверяет:
1. Адаптер linq_adapter (загрузка, инференс, формат тензора);
2. Фабрику движков create_inference_engine (LINQ_TPU, LINQ_REMOTE);
3. Препроцессинг, постпроцессинг и структуру метрик LinQTPUEngine.
"""

from __future__ import annotations

import os
import sys
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
import numpy as np

from engine.inference.base import InferenceResult
from engine.inference.factory import create_inference_engine
from engine.inference.linq_tpu import LinQTPUEngine
import linq_adapter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = str(PROJECT_ROOT / "models" / "tpu" / "safety_yolov8n_b1_o1_h1m.tpu")


@contextmanager
def mock_pytpu_sdk(num_classes: int = 3):
    @contextmanager
    def session():
        def sync(inputs):
            return {"output0": np.zeros((1, 4 + num_classes, 100), dtype=np.float32)}
        yield SimpleNamespace(sync=sync, run=sync)

    @contextmanager
    def program(path):
        yield SimpleNamespace(inference=session)

    @contextmanager
    def device(path):
        yield SimpleNamespace(load=program)

    mock_mod = SimpleNamespace(Device=SimpleNamespace(list_devices=lambda: ["/dev/tpu0"], open=device))
    with patch.dict(sys.modules, {"pytpu": mock_mod}):
        yield


class TestLinQIntegration(unittest.TestCase):
    def setUp(self):
        self.dummy_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        self.dummy_tensor = np.random.uniform(0.0, 1.0, (1, 3, 640, 640)).astype(np.float32)

    def test_linq_adapter_load_and_run(self):
        """Проверка интерфейса linq_adapter: load -> run(tensor) -> ndarray."""
        with mock_pytpu_sdk():
            infer_fn = linq_adapter.load(MODEL_PATH)
            self.assertTrue(callable(infer_fn))

            out = infer_fn(self.dummy_tensor)
            self.assertIsInstance(out, np.ndarray)
            self.assertIn(out.ndim, (2, 3))
            self.assertGreater(out.size, 0)

    def test_linq_tpu_engine_initialization(self):
        """Проверка создания LinQTPUEngine и инференса."""
        with mock_pytpu_sdk():
            engine = LinQTPUEngine(
                model_path=MODEL_PATH,
                conf_threshold=0.3,
                input_size=(640, 640),
                class_names={0: "person", 1: "helmet", 2: "vest"},
            )
            self.assertTrue(engine.is_loaded)

            # Проверка препроцессинга
            tensor, meta = engine.preprocess(self.dummy_frame)
            self.assertEqual(tensor.shape, (1, 3, 640, 640))
            self.assertEqual(tensor.dtype, np.float32)
            self.assertIn("scale", meta)

            # Проверка инференса
            res = engine.infer(self.dummy_frame)
            self.assertIsInstance(res, InferenceResult)
            self.assertIn("LINQ_TPU", res.metrics.backend_name)
            self.assertGreater(res.metrics.total_time_ms, 0.0)
            self.assertGreater(res.metrics.fps, 0.0)

    def test_factory_creates_linq_backends(self):
        """Проверка фабрики create_inference_engine для LINQ_TPU и LINQ_REMOTE."""
        with mock_pytpu_sdk():
            engine_tpu = create_inference_engine(
                backend="LINQ_TPU",
                model_path=MODEL_PATH,
                class_names={0: "person", 1: "helmet"},
            )
            self.assertIsInstance(engine_tpu, LinQTPUEngine)

            engine_remote = create_inference_engine(
                backend="LINQ_REMOTE",
                model_path=MODEL_PATH,
                remote_url="http://10.0.114.15:8080",
                class_names={0: "person", 1: "helmet"},
            )
            self.assertIsInstance(engine_remote, LinQTPUEngine)
            self.assertEqual(engine_remote.remote_url, "http://10.0.114.15:8080")


if __name__ == "__main__":
    unittest.main()
