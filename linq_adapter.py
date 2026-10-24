"""
Адаптер инференса нейронных сетей для LinQ TPU (H1M).
Реализует интерфейс load(program_path) -> callable(tensor) -> ndarray
согласно спецификации SDK tpu_framework и usage_example_python_api.

При наличии физического устройства LinQ TPU (/dev/tpu*) использует драйвер pytpu.
При разработке и тестировании на рабочей машине (Windows / macOS / Linux без TPU)
автоматически включает безопасный режим эмуляции через локальный ONNX / Mock.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable, Optional
import numpy as np

logger = logging.getLogger("linq.adapter")

try:
    import pytpu as tpu
    HAS_PYTPU = True
except ImportError:
    tpu = None
    HAS_PYTPU = False


def load(program_path: str, input_node: str = "images", output_node: str = "output0") -> Callable[[np.ndarray], np.ndarray]:
    """
    Загружает скомпилированную программу .tpu в ускоритель LinQ TPU
    и возвращает функцию инференса.
    """
    prog_path = Path(program_path)
    
    # Проверка наличия библиотеки pytpu и физического TPU
    tpu_device = None
    tpu_program = None
    inference_session = None

    if HAS_PYTPU:
        try:
            available_devices = tpu.Device.list_devices()
            if available_devices:
                logger.info("Обнаружены устройства LinQ TPU: %s", available_devices)
                tpu_device = tpu.Device.open(available_devices[0])
                if prog_path.exists():
                    tpu_program = tpu_device.load(str(prog_path))
                    inference_session = tpu_program.inference()
                    logger.info("Программа LinQ TPU успешно загружена: %s", prog_path)
                else:
                    logger.warning("Файл программы TPU не найден: %s. Переход в режим эмуляции.", prog_path)
            else:
                logger.warning("Устройства LinQ TPU не найдены в /dev/tpu*. Включен режим эмуляции.")
        except Exception as e:
            logger.warning("Ошибка инициализации аппаратного LinQ TPU: %s. Включен режим эмуляции.", e)

    # Если TPU инициализирован успешно
    if inference_session is not None:
        def run_tpu(tensor: np.ndarray) -> np.ndarray:
            """
            Аппаратный инференс на чипе LinQ TPU H1M.
            Ожидает тензор (1, 3, H, W) в float32.
            """
            tensor = np.ascontiguousarray(tensor, dtype=np.float32)
            inputs = {input_node: tensor}
            outputs = inference_session.run(inputs)
            if isinstance(outputs, dict):
                return outputs.get(output_node, next(iter(outputs.values())))
            return outputs

        return run_tpu

    # --- Проверка удаленного сервиса LinQ TPU (через LINQ_TPU_URL по VPN) ---
    remote_url = os.getenv("LINQ_TPU_URL")
    if remote_url:
        try:
            import urllib.request
            health_req = urllib.request.Request(f"{remote_url.rstrip('/')}/health", headers={"User-Agent": "LinQClient/1.0"})
            with urllib.request.urlopen(health_req, timeout=2.0) as resp:
                if resp.status == 200:
                    logger.info("Успешное подключение к удаленному LinQ TPU сервису: %s", remote_url)
                    def run_remote_tpu(tensor: np.ndarray) -> np.ndarray:
                        tensor = np.ascontiguousarray(tensor, dtype=np.float32)
                        infer_url = f"{remote_url.rstrip('/')}/infer_raw"
                        post_req = urllib.request.Request(
                            infer_url,
                            data=tensor.tobytes(),
                            headers={"Content-Type": "application/octet-stream", "User-Agent": "LinQClient/1.0"}
                        )
                        with urllib.request.urlopen(post_req, timeout=10.0) as post_resp:
                            resp_bytes = post_resp.read()
                            out = np.frombuffer(resp_bytes, dtype=np.float32)
                            if out.size == 1 * 21 * 8400:
                                return out.reshape((1, 21, 8400))
                            return out
                    return run_remote_tpu
        except Exception as e:
            logger.warning("Удаленный LinQ TPU сервис %s недоступен: %s. Переход к локальному фоллбэку.", remote_url, e)

    # --- Режим эмуляции / локального фоллбэка ---
    logger.info("[LinQ Adapter] Запуск в режиме эмуляции (HAL Fallback).")
    fallback_onnx = Path("models/onnx/safety_yolov8n.onnx")
    if not fallback_onnx.exists():
        fallback_onnx = Path("models/onnx/yolov8n_safety_640.onnx")

    ort_session = None
    if fallback_onnx.exists():
        try:
            import onnxruntime as ort
            ort_session = ort.InferenceSession(str(fallback_onnx), providers=["CPUExecutionProvider"])
            inp_name = ort_session.get_inputs()[0].name
            out_name = ort_session.get_outputs()[0].name
            logger.info("Эмуляция LinQ TPU через локальный ONNX: %s", fallback_onnx)
        except Exception as e:
            logger.warning("Не удалось инициализировать ONNXRuntime для эмуляции: %s", e)

    def run_emulated(tensor: np.ndarray) -> np.ndarray:
        tensor = np.ascontiguousarray(tensor, dtype=np.float32)
        if ort_session is not None:
            return ort_session.run([out_name], {inp_name: tensor})[0]

        # Синтетический тензор формата YOLOv8: (1, 4 + 17_classes, 8400)
        batch = tensor.shape[0] if tensor.ndim == 4 else 1
        num_classes = 17
        num_anchors = 8400
        mock_output = np.zeros((batch, 4 + num_classes, num_anchors), dtype=np.float32)
        # Добавляем синтетическую детекцию человека
        mock_output[0, 0, 0] = 320.0   # cx
        mock_output[0, 1, 0] = 240.0   # cy
        mock_output[0, 2, 0] = 100.0   # w
        mock_output[0, 3, 0] = 200.0   # h
        mock_output[0, 4 + 9, 0] = 0.95  # person conf
        return mock_output

    return run_emulated
