"""
Базовые абстракции и структуры данных движка правил промышленной безопасности.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from engine.inference.base import BoundingBox
from engine.tracking.types import TrackedObject


class ViolationSeverity(Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RuleViolation:
    """
    Сырой инцидент нарушения правила ТБ на конкретном кадре.
    """
    rule_name: str
    rule_id: str
    severity: ViolationSeverity
    timestamp: float
    camera_id: str
    track_id: int
    involved_track_ids: List[int] = field(default_factory=list)
    description: str = ""
    bbox: Optional[BoundingBox] = None
    zone_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    violation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return {
            "violation_id": self.violation_id,
            "rule_name": self.rule_name,
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "camera_id": self.camera_id,
            "track_id": self.track_id,
            "involved_track_ids": self.involved_track_ids,
            "description": self.description,
            "bbox": self.bbox.as_xyxy() if self.bbox else None,
            "zone_id": self.zone_id,
            "metadata": self.metadata,
        }


@dataclass
class FrameContext:
    """
    Контекст текущего обрабатываемого кадра.
    """
    frame_id: int
    timestamp: float = field(default_factory=time.time)
    camera_id: str = "camera_01"
    frame_width: int = 1920
    frame_height: int = 1080
    fps: float = 25.0
    all_detections: List[Any] = field(default_factory=list)


class BaseRule(ABC):
    """
    Абстрактный класс правила техники безопасности.
    """

    def __init__(self, name: str, is_enabled: bool = True) -> None:
        self.name = name
        self.is_enabled = is_enabled

    def reset(self) -> None:
        """Clear temporal state while preserving rule configuration."""

    @abstractmethod
    def evaluate(self, tracks: List[TrackedObject], context: FrameContext) -> List[RuleViolation]:
        """
        Проверка выполнения правила над текущим набором сопровождаемых объектов.
        """
        pass
