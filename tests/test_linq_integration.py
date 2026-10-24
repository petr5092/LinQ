"""
Тестирование интеграции с аппаратным ускорителем LinQ TPU (H1M) и слоем HAL.
Проверяет:
1. Адаптер linq_adapter (загрузка, инференс, формат тензора);
2. Фабрику движков create_inference_engine (LINQ_TPU, LINQ_REMOTE);
3. Препроцессинг, постпроцессинг и структуру метрик LinQTPUEngine.
"""

from __future__ import annotations

import os
import unittest
import numpy as np

from engine.inference.base import InferenceResult
from engine.inference.factory import create_inference_engine
from engine.inference.linq_tpu import LinQTPUEngine
import linq_adapter


class TestLinQIntegration(unittest.TestCase):
    def setUp(self):
        self.dummy_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        self.dummy_tensor = np.random.uniform(0.0, 1.0, (1, 3, 640, 640)).astype(np.float32)

    def test_linq_adapter_load_and_run(self):
        """Проверка интерфейса linq_adapter: load -> run(tensor) -> ndarray."""
        infer_fn = linq_adapter.load("models/tpu/test_safety.tpu")
        self.assertTrue(callable(infer_fn))

        out = infer_fn(self.dummy_tensor)
        self.assertIsInstance(out, np.ndarray)
        # Выходной тензор должен быть 2D или 3D
        self.assertIn(out.ndim, (2, 3))
        # Проверяем, что выход не пустой
        self.assertGreater(out.size, 0)

    def test_linq_tpu_engine_initialization(self):
        """Проверка создания LinQTPUEngine в режиме HAL fallback / эмуляции."""
        engine = LinQTPUEngine(
            model_path="models/tpu/safety_yolov8_h1m.tpu",
            conf_threshold=0.3,
            input_size=(640, 640),
            class_names={0: "person", 4: "helmet", 12: "vest"},
        )
        self.assertTrue(engine.is_loaded)
        # В среде без физического чипа должен автоматически включиться безопасный режим
        self.assertTrue(engine.is_emulated or hasattr(engine, "is_remote"))

        # Проверка препроцессинга
        tensor, meta = engine.preprocess(self.dummy_frame)
        self.assertEqual(tensor.shape, (1, 3, 640, 640))
        self.assertEqual(tensor.dtype, np.float32)
        self.assertIn("scale", meta)

        # Проверка инференса
        res = engine.infer(self.dummy_frame)
        self.assertIsInstance(res, InferenceResult)
        self.assertIn("LinQ_TPU_H1M", res.metrics.backend_name)
        self.assertGreater(res.metrics.total_time_ms, 0.0)
        self.assertGreater(res.metrics.fps, 0.0)

    def test_factory_creates_linq_backends(self):
        """Проверка фабрики create_inference_engine для LINQ_TPU и LINQ_REMOTE."""
        engine_tpu = create_inference_engine(backend="LINQ_TPU")
        self.assertIsInstance(engine_tpu, LinQTPUEngine)

        engine_remote = create_inference_engine(backend="LINQ_REMOTE", remote_url="http://10.0.114.15:8080")
        self.assertIsInstance(engine_remote, LinQTPUEngine)
        self.assertEqual(engine_remote.remote_url, "http://10.0.114.15:8080")


if __name__ == "__main__":
    unittest.main()
