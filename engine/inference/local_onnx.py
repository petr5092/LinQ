"""
Local ONNX Engine — Локальный инференс на базе ONNXRuntime (CPU/CUDA).
Используется как фоллбэк при разработке и отладке без физического LinQ TPU.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    ort = None

from engine.inference.base import (
    BaseInferenceEngine,
    BoundingBox,
    Detection,
    InferenceMetrics,
    InferenceResult,
)


class LocalONNXEngine(BaseInferenceEngine):
    """
    Инференс-движок на базе ONNXRuntime с поддержкой архитектур YOLO (v8/v9/v11).
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        conf_threshold: float = 0.35,
        iou_threshold: float = 0.45,
        input_size: Tuple[int, int] = (640, 640),
        class_names: Optional[Dict[int, str]] = None,
        providers: Optional[List[str]] = None,
    ) -> None:
        super().__init__(
            model_path=model_path,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            input_size=input_size,
            class_names=class_names,
        )
        self.providers = providers or ["CPUExecutionProvider"]
        self.session: Optional[ort.InferenceSession] = None
        self.input_name: str = ""
        self.output_names: List[str] = []

        if self.model_path and os.path.exists(self.model_path):
            self.load()

    def load(self, model_path: Optional[str] = None) -> None:
        path = model_path or self.model_path
        if not path:
            raise ValueError("[LocalONNXEngine] Путь к модели не указан.")
        if not os.path.exists(path):
            raise FileNotFoundError(f"[LocalONNXEngine] Файл модели не найден: {path}")

        if ort is None:
            raise RuntimeError("[LocalONNXEngine] Библиотека onnxruntime не установлена.")

        session_options = ort.SessionOptions()
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        session_options.intra_op_num_threads = max(1, os.cpu_count() or 4)

        self.session = ort.InferenceSession(path, sess_options=session_options, providers=self.providers)
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [out.name for out in self.session.get_outputs()]

        # Обновляем input_size из метаданных графа при наличии фиксированных размерностей
        shape = self.session.get_inputs()[0].shape
        if len(shape) == 4 and isinstance(shape[2], int) and isinstance(shape[3], int):
            self.input_size = (shape[3], shape[2])  # width, height

        self.model_path = path
        self.is_loaded = True

    def preprocess(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Letterbox-масштабирование с сохранением пропорций и добавлением полей.
        Возвращает тензор (1, 3, H, W) в формате float32 [0.0, 1.0] и метаданные масштабирования.
        """
        orig_h, orig_w = frame.shape[:2]
        target_w, target_h = self.input_size

        # Расчет коэффициента масштабирования
        scale = min(target_w / orig_w, target_h / orig_h)
        new_w = int(round(orig_w * scale))
        new_h = int(round(orig_h * scale))

        # Ресайз
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # Симметричный паддинг
        pad_x = (target_w - new_w) / 2.0
        pad_y = (target_h - new_h) / 2.0

        top = int(round(pad_y - 0.1))
        bottom = int(round(pad_y + 0.1))
        left = int(round(pad_x - 0.1))
        right = int(round(pad_x + 0.1))

        # Заливка серым фоном 114 (стандарт YOLO)
        padded = cv2.copyMakeBorder(
            resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114)
        )

        # Конвертация BGR -> RGB, HWC -> CHW, нормализация в [0, 1]
        rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
        chw = np.transpose(rgb, (2, 0, 1)).astype(np.float32) / 255.0
        tensor = np.expand_dims(chw, axis=0)

        meta = {
            "orig_shape": (orig_h, orig_w),
            "scale": scale,
            "pad_x": pad_x,
            "pad_y": pad_y,
        }
        return tensor, meta

    def postprocess(self, raw_output: Any, meta: Dict[str, Any]) -> List[Detection]:
        """
        Разбор выходного тензора YOLO (поддержка YOLOv8/v9 shape [1, 4+C, N] или [1, N, 4+C]).
        """
        if isinstance(raw_output, (list, tuple)):
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
        num_classes = num_attrs - 4

        boxes = output[:, :4]  # xc, yc, w, h
        class_scores = output[:, 4:]  # вероятности классов

        max_scores = np.max(class_scores, axis=1)
        class_ids = np.argmax(class_scores, axis=1)

        # Фильтрация по порогу уверенности
        mask = max_scores >= self.conf_threshold
        if not np.any(mask):
            return []

        boxes = boxes[mask]
        scores = max_scores[mask]
        class_ids = class_ids[mask]

        # Преобразование [xc, yc, w, h] -> [x1, y1, x2, y2]
        xc = boxes[:, 0]
        yc = boxes[:, 1]
        w = boxes[:, 2]
        h = boxes[:, 3]

        x1 = xc - w / 2.0
        y1 = yc - h / 2.0
        x2 = xc + w / 2.0
        y2 = yc + h / 2.0

        # Коррекция паддинга и масштаба обратно к оригинальному разрешению кадра
        scale = meta["scale"]
        pad_x = meta["pad_x"]
        pad_y = meta["pad_y"]
        orig_h, orig_w = meta["orig_shape"]

        x1 = (x1 - pad_x) / scale
        y1 = (y1 - pad_y) / scale
        x2 = (x2 - pad_x) / scale
        y2 = (y2 - pad_y) / scale

        # NMS (Non-Maximum Suppression)
        detections: List[Detection] = []
        unique_classes = np.unique(class_ids)

        for cls_id in unique_classes:
            cls_mask = class_ids == cls_id
            cls_x1 = x1[cls_mask]
            cls_y1 = y1[cls_mask]
            cls_x2 = x2[cls_mask]
            cls_y2 = y2[cls_mask]
            cls_scores = scores[cls_mask]

            keep_indices = self._nms_indices(cls_x1, cls_y1, cls_x2, cls_y2, cls_scores, self.iou_threshold)

            class_name = self.class_names.get(int(cls_id), f"class_{cls_id}")
            for idx in keep_indices:
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
        """Быстрая векторная реализация NMS на NumPy."""
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
        if not self.is_loaded or self.session is None:
            raise RuntimeError("[LocalONNXEngine] Модель не загружена. Вызовите load() перед infer().")

        orig_shape = frame.shape

        # 1. Препроцессинг
        t0 = time.perf_counter()
        tensor, meta = self.preprocess(frame)
        t1 = time.perf_counter()

        # 2. Инференс на CPU
        outputs = self.session.run(self.output_names, {self.input_name: tensor})
        t2 = time.perf_counter()

        # 3. Постпроцессинг
        detections = self.postprocess(outputs, meta)
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
            backend_name="ONNX_CPU",
        )

        return InferenceResult(
            detections=detections,
            metrics=metrics,
            original_shape=orig_shape,
        )
