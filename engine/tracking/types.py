"""
Типы данных и структуры для трекинга объектов во времени.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple
import numpy as np

from engine.inference.base import BoundingBox


class TrackState(Enum):
    NEW = 1
    TRACKED = 2
    LOST = 3
    REMOVED = 4


@dataclass
class TrackedObject:
    """
    Информация об объекте, сопровождаемом трекером во времени.
    """
    track_id: int
    class_id: int
    class_name: str
    bbox: BoundingBox
    confidence: float
    state: TrackState = TrackState.NEW
    age: int = 1
    hits: int = 1
    time_since_update: int = 0
    velocity: Tuple[float, float] = (0.0, 0.0)  # (vx, vy) пикселей/кадр
    speed: float = 0.0  # модуль скорости в пикселях/кадр
    history: List[Tuple[float, float]] = field(default_factory=list)  # координаты стоп (xc, y_bottom)
    is_confirmed: bool = False

    @property
    def bottom_center(self) -> Tuple[float, float]:
        return self.bbox.bottom_center

    @property
    def center(self) -> Tuple[float, float]:
        return self.bbox.center

    @property
    def aspect_ratio(self) -> float:
        return self.bbox.aspect_ratio

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "class_name": self.class_name,
            "bbox": self.bbox.as_xyxy(),
            "confidence": round(self.confidence, 3),
            "speed": round(self.speed, 2),
            "state": self.state.name,
            "age": self.age,
        }
