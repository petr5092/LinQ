"""
LinQ TPU Inference Engine — Аппаратное ускорение на чипах LinQ TPU (архитектура TPU_H1M).
Интеграция с нативным рантаймом pytpu и поддержка вычислений FP19 / INT8.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

try:
    import pytpu as tpu
    HAS_PYTPU = True
except ImportError:
    tpu = None
    HAS_PYTPU = False

from engine.inference.base import (
    BaseInferenceEngine,
    BoundingBox,
    Detection,
    InferenceMetrics,
    InferenceResult,
)


class LinQTPUEngine(BaseInferenceEngine):
    """
    Инференс-движок на базе отечественного ускорителя LinQ TPU (чип H1M).
    Работает через нативный API `pytpu`. При запуске вне аппаратного стенда
    (например, на машине разработчика) переходит в режим эмуляции/фоллбэка.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        conf_threshold: float = 0.35,
        iou_threshold: float = 0.45,
        input_size: Tuple[int, int] = (640, 640),
        class_names: Optional[Dict[int, str]] = None,
        device_index: int = 0,
        input_node_name: str = "images",
        output_node_name: str = "output0",
        remote_url: Optional[str] = None,
    ) -> None:
        super().__init__(
            model_path=model_path,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            input_size=input_size,
            class_names=class_names,
        )
        self.device_index = device_index
        self.input_node_name = input_node_name
        self.output_node_name = output_node_name

        self.remote_url = remote_url or os.getenv("LINQ_TPU_URL")
        self._tpu_device = None
        self._tpu_program = None
        self._inference_session = None
        self.is_emulated: bool = False
        self.is_remote: bool = False

        if self.model_path:
            self.load()

    def load(self, model_path: Optional[str] = None) -> None:
        path = model_path or self.model_path
        if not path:
            raise ValueError("[LinQTPUEngine] Путь к TPU-программе (.tpu) не указан.")

        self.model_path = path

        # Проверка удаленного подключения к TPU сервису по VPN
        if self.remote_url:
            try:
                import urllib.request
                health_req = urllib.request.Request(f"{self.remote_url.rstrip('/')}/health", headers={"User-Agent": "LinQTPU/1.0"})
                with urllib.request.urlopen(health_req, timeout=2.0) as resp:
                    if resp.status == 200:
                        self.is_remote = True
                        self.is_emulated = False
                        self.is_loaded = True
                        print(f"[LinQTPUEngine] Подключено к удаленному LinQ TPU сервису: {self.remote_url}")
                        return
            except Exception as e:
                print(f"[LinQTPUEngine] Удаленный TPU {self.remote_url} недоступен: {e}. Проверка локального устройства...")

        # Проверка доступности физического устройства LinQ TPU
        if HAS_PYTPU:
            try:
                available_devices = tpu.Device.list_devices()
                if available_devices:
                    dev_path = available_devices[self.device_index]
                    self._tpu_device = tpu.Device.open(dev_path)
                    self._tpu_program = self._tpu_device.load(self.model_path)
                    self._inference_session = self._tpu_program.inference()
                    self.is_emulated = False
                    self.is_loaded = True
                    print(f"[LinQTPUEngine] Успешно инициализирован аппаратный чип {dev_path} (H1M)")
                    return
            except Exception as e:
                print(f"[LinQTPUEngine] Ошибка открытия LinQ TPU устройства: {e}. Переход в режим эмуляции.")

        # Режим эмуляции для запуска вне физического стенда с TPU
        self.is_emulated = True
        self.is_loaded = True
        print("[LinQTPUEngine] Аппаратное устройство /dev/tpu* недоступно. Активен режим эмуляции HAL.")

    def preprocess(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Препроцессинг кадра со строгим соблюдением фиксированного входного шейпа [1, 3, H, W]
        (динамические размерности чипом TPU_H1M не поддерживаются).
        """
        orig_h, orig_w = frame.shape[:2]
        target_w, target_h = self.input_size

        scale = min(target_w / orig_w, target_h / orig_h)
        new_w = int(round(orig_w * scale))
        new_h = int(round(orig_h * scale))

        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        pad_x = (target_w - new_w) / 2.0
        pad_y = (target_h - new_h) / 2.0

        top = int(round(pad_y - 0.1))
        bottom = int(round(pad_y + 0.1))
        left = int(round(pad_x - 0.1))
        right = int(round(pad_x + 0.1))

        padded = cv2.copyMakeBorder(
            resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114)
        )

        rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
        chw = np.transpose(rgb, (2, 0, 1)).astype(np.float32) / 255.0
        tensor = np.ascontiguousarray(np.expand_dims(chw, axis=0))

        meta = {
            "orig_shape": (orig_h, orig_w),
            "scale": scale,
            "pad_x": pad_x,
            "pad_y": pad_y,
        }
        return tensor, meta

    def postprocess(self, raw_output: Any, meta: Dict[str, Any]) -> List[Detection]:
        if raw_output is None:
            return []

        if isinstance(raw_output, dict):
            output = raw_output.get(self.output_node_name, list(raw_output.values())[0])
        elif isinstance(raw_output, (list, tuple)):
            output = raw_output[0]
        else:
            output = raw_output
        if output.ndim == 3 and output.shape[0] == 1:
            output = output[0]
        elif output.ndim > 2:
            output = np.squeeze(output)

        if output.ndim == 1:
            output = np.expand_dims(output, axis=0)

        if output.ndim != 2:
            return []

        # Приводим к размерности (N, 4 + C), где N — количество кандидатов
        if output.shape[1] < 5 or (len(self.class_names) > 0 and output.shape[0] == 4 + len(self.class_names)):
            output = output.T

        num_candidates, num_attrs = output.shape
        if num_attrs < 5:
            return []

        boxes = output[:, :4]
        class_scores = output[:, 4:]

        max_scores = np.max(class_scores, axis=1)
        class_ids = np.argmax(class_scores, axis=1)

        mask = max_scores >= self.conf_threshold
        if not np.any(mask):
            return []

        boxes = boxes[mask]
        scores = max_scores[mask]
        class_ids = class_ids[mask]

        xc = boxes[:, 0]
        yc = boxes[:, 1]
        w = boxes[:, 2]
        h = boxes[:, 3]

        x1 = xc - w / 2.0
        y1 = yc - h / 2.0
        x2 = xc + w / 2.0
        y2 = yc + h / 2.0

        scale = meta["scale"]
        pad_x = meta["pad_x"]
        pad_y = meta["pad_y"]
        orig_h, orig_w = meta["orig_shape"]

        x1 = (x1 - pad_x) / scale
        y1 = (y1 - pad_y) / scale
        x2 = (x2 - pad_x) / scale
        y2 = (y2 - pad_y) / scale

        detections: List[Detection] = []
        unique_classes = np.unique(class_ids)

        for cls_id in unique_classes:
            cls_mask = class_ids == cls_id
            cls_x1 = x1[cls_mask]
            cls_y1 = y1[cls_mask]
            cls_x2 = x2[cls_mask]
            cls_y2 = y2[cls_mask]
            cls_scores = scores[cls_mask]

            keep = self._nms_indices(cls_x1, cls_y1, cls_x2, cls_y2, cls_scores, self.iou_threshold)
            class_name = self.class_names.get(int(cls_id), f"class_{cls_id}")

            for idx in keep:
                bbox = BoundingBox(
                    x1=float(cls_x1[idx]),
                    y1=float(cls_y1[idx]),
                    x2=float(cls_x2[idx]),
                    y2=float(cls_y2[idx]),
                ).clip(orig_w, orig_h)

                detections.append(
                    Detection(
                        bbox=bbox,
                        confidence=float(cls_scores[idx]),
                        class_id=int(cls_id),
                        class_name=class_name,
                    )
                )

        return detections

    @staticmethod
    def _nms_indices(
        x1: np.ndarray,
        y1: np.ndarray,
        x2: np.ndarray,
        y2: np.ndarray,
        scores: np.ndarray,
        iou_thresh: float,
    ) -> List[int]:
        areas = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
        order = scores.argsort()[::-1]

        keep: List[int] = []
        while order.size > 0:
            i = order[0]
            keep.append(int(i))
            if order.size == 1:
                break

            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            inter = w * h

            union = areas[i] + areas[order[1:]] - inter
            iou = np.where(union > 0.0, inter / union, 0.0)

            inds = np.where(iou <= iou_thresh)[0]
            order = order[inds + 1]

        return keep

    def infer(self, frame: np.ndarray) -> InferenceResult:
        if not self.is_loaded:
            raise RuntimeError("[LinQTPUEngine] Ускоритель не инициализирован. Вызовите load().")

        orig_shape = frame.shape

        t0 = time.perf_counter()
        tensor, meta = self.preprocess(frame)
        t1 = time.perf_counter()

        if not self.is_emulated and self._inference_session is not None:
            # Аппаратный инференс на плате LinQ TPU через драйвер pytpu
            input_dict = {self.input_node_name: tensor}
            raw_output = self._inference_session.run(input_dict)
        elif self.is_remote and self.remote_url:
            # Инференс через удаленный сервис LinQ TPU по VPN
            import urllib.request
            post_req = urllib.request.Request(
                f"{self.remote_url.rstrip('/')}/infer_raw",
                data=tensor.tobytes(),
                headers={"Content-Type": "application/octet-stream", "User-Agent": "LinQTPU/1.0"}
            )
            with urllib.request.urlopen(post_req, timeout=10.0) as resp:
                resp_bytes = resp.read()
                raw_output = np.frombuffer(resp_bytes, dtype=np.float32)
                nc = len(self.class_names)
                if raw_output.size == 1 * (4 + nc) * 8400:
                    raw_output = raw_output.reshape((1, 4 + nc, 8400))
        else:
            # Эмуляция вывода с типичной задержкой чипа LinQ TPU H1M (~12-18 мс)
            time.sleep(0.015)
            # Возвращаем структуру для постпроцессинга
            raw_output = np.zeros((1, 4 + len(self.class_names), 84), dtype=np.float32)

        t2 = time.perf_counter()
        detections = self.postprocess(raw_output, meta)
        t3 = time.perf_counter()

        prep_ms = (t1 - t0) * 1000.0
        inf_ms = (t2 - t1) * 1000.0
        post_ms = (t3 - t2) * 1000.0
        tot_ms = (t3 - t0) * 1000.0
        fps = 1000.0 / tot_ms if tot_ms > 0 else 0.0

        metrics = InferenceMetrics(
            preprocess_time_ms=round(prep_ms, 2),
            inference_time_ms=round(inf_ms, 2),
            postprocess_time_ms=round(post_ms, 2),
            total_time_ms=round(tot_ms, 2),
            fps=round(fps, 1),
            backend_name="LinQ_TPU_H1M" + ("_Remote" if self.is_remote else ("_Emulated" if self.is_emulated else "")),
        )

        return InferenceResult(
            detections=detections,
            metrics=metrics,
            original_shape=orig_shape,
        )

    def close(self) -> None:
        if self._inference_session is not None:
            try:
                self._inference_session.close()
            except Exception:
                pass
            self._inference_session = None

        if self._tpu_program is not None:
            try:
                self._tpu_program.close()
            except Exception:
                pass
            self._tpu_program = None

        if self._tpu_device is not None:
            try:
                self._tpu_device.close()
            except Exception:
                pass
            self._tpu_device = None

        super().close()
