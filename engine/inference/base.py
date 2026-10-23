"""
Hardware Abstraction Layer (HAL) — Базовые интерфейсы и структуры данных инференса.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np


@dataclass
class BoundingBox:
    """
    Координаты ограничивающего прямоугольника объекта (x1, y1, x2, y2).
    """
    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self) -> None:
        if self.x2 < self.x1:
            self.x1, self.x2 = self.x2, self.x1
        if self.y2 < self.y1:
            self.y1, self.y2 = self.y2, self.y1

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    @property
    def bottom_center(self) -> Tuple[float, float]:
        """Нижняя опорная точка (стопы человека) для геометрии зон."""
        return ((self.x1 + self.x2) / 2.0, self.y2)

    @property
    def head_box(self) -> "BoundingBox":
        """Верхняя треть прямоугольника (область головы для детекции каски)."""
        h_third = self.height * 0.33
        return BoundingBox(self.x1, self.y1, self.x2, self.y1 + h_third)

    @property
    def torso_box(self) -> "BoundingBox":
        """Средняя треть прямоугольника (область торса для детекции жилета)."""
        h_third = self.height * 0.33
        return BoundingBox(self.x1, self.y1 + h_third * 0.6, self.x2, self.y1 + h_third * 2.2)

    @property
    def aspect_ratio(self) -> float:
        """Соотношение ширины к высоте (w / h). Для лежащего человека > 1.0."""
        return self.width / (self.height + 1e-6)

    def as_xyxy(self) -> Tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)

    def as_int_xyxy(self) -> Tuple[int, int, int, int]:
        return (int(round(self.x1)), int(round(self.y1)), int(round(self.x2)), int(round(self.y2)))

    def as_xywh(self) -> Tuple[float, float, float, float]:
        return (self.x1, self.y1, self.width, self.height)

    def clip(self, max_width: int, max_height: int) -> "BoundingBox":
        """Ограничивает координаты рамки пределами изображения."""
        return BoundingBox(
            x1=max(0.0, min(float(max_width), self.x1)),
            y1=max(0.0, min(float(max_height), self.y1)),
            x2=max(0.0, min(float(max_width), self.x2)),
            y2=max(0.0, min(float(max_height), self.y2)),
        )

    def iou(self, other: "BoundingBox") -> float:
        """Вычисляет метрику Intersection over Union (IoU) между двумя рамками."""
        inter_x1 = max(self.x1, other.x1)
        inter_y1 = max(self.y1, other.y1)
        inter_x2 = min(self.x2, other.x2)
        inter_y2 = min(self.y2, other.y2)

        inter_w = max(0.0, inter_x2 - inter_x1)
        inter_h = max(0.0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h

        union_area = self.area + other.area - inter_area
        if union_area <= 0.0:
            return 0.0
        return inter_area / union_area


@dataclass
class Detection:
    """
    Результат детекции единичного объекта на кадре.
    """
    bbox: BoundingBox
    confidence: float
    class_id: int
    class_name: str
    feature_vector: Optional[np.ndarray] = None


@dataclass
class InferenceMetrics:
    """
    Метрики производительности инференса (задержка и пропускная способность).
    """
    preprocess_time_ms: float = 0.0
    inference_time_ms: float = 0.0
    postprocess_time_ms: float = 0.0
    total_time_ms: float = 0.0
    fps: float = 0.0
    backend_name: str = ""


@dataclass
class InferenceResult:
    """
    Полный результат работы инференс-ядра на одном кадре.
    """
    detections: List[Detection] = field(default_factory=list)
    metrics: InferenceMetrics = field(default_factory=InferenceMetrics)
    original_shape: Tuple[int, int, int] = (0, 0, 0)  # H, W, C


class BaseInferenceEngine(ABC):
    """
    Абстрактный класс слоя аппаратного ускорения инференса нейросетей (HAL).
    Обеспечивает унифицированный контракт для LinQ TPU и локального ONNX CPU.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        conf_threshold: float = 0.35,
        iou_threshold: float = 0.45,
        input_size: Tuple[int, int] = (640, 640),
        class_names: Optional[Dict[int, str]] = None,
    ) -> None:
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.input_size = input_size  # (width, height)
        self.class_names = class_names or {
            0: "person",
            1: "forklift",
            2: "machinery",
            3: "helmet",
            4: "no_helmet",
            5: "vest",
            6: "no_vest",
        }
        self.is_loaded: bool = False

    @abstractmethod
    def load(self, model_path: Optional[str] = None) -> None:
        """Загрузка скомпилированной программы или графа модели."""
        pass

    @abstractmethod
    def infer(self, frame: np.ndarray) -> InferenceResult:
        """
        Выполняет полный цикл инференса (препроцессинг -> запуск на ускорителе -> постпроцессинг).
        :param frame: BGR-изображение (H, W, 3)
        :return: InferenceResult со списком детекций и замерами времени
        """
        pass

    @abstractmethod
    def preprocess(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Преобразование кадра в статичный тензор заданной размерности (letterbox/нормализация).
        """
        pass

    @abstractmethod
    def postprocess(self, raw_output: Any, meta: Dict[str, Any]) -> List[Detection]:
        """
        Преобразование выходных тензоров сети в список объектов Detection с фильтрацией и NMS.
        """
        pass

    def close(self) -> None:
        """Освобождение аппаратных дескрипторов и ресурсов."""
        self.is_loaded = False

    def __enter__(self) -> "BaseInferenceEngine":
        if not self.is_loaded and self.model_path:
            self.load()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
