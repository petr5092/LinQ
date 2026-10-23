"""
Типы данных и состояния жизненного цикла инцидента (Anti-Spam & Deduplication).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import uuid
from typing import Any, Dict, List, Optional

from engine.inference.base import BoundingBox
from engine.rules.base import ViolationSeverity


class IncidentState(Enum):
    PENDING = "PENDING"        # Накапливает подтверждения (debounce)
    CONFIRMED = "CONFIRMED"    # Подтверждено, готово к мгновенной отправке оператору
    ACTIVE = "ACTIVE"          # Длящееся нарушение, повторный спам заблокирован (cooldown)
    RESOLVED = "RESOLVED"      # Нарушение прекратилось, инцидент закрыт
    EXPIRED = "EXPIRED"        # Таймаут кулдауна истек


@dataclass
class ConfirmedIncident:
    """
    Верифицированный инцидент промышленной безопасности, очищенный от дребезга и дублей.
    """
    incident_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    rule_id: str = ""
    severity: ViolationSeverity = ViolationSeverity.HIGH
    camera_id: str = ""
    track_id: int = 0
    involved_track_ids: List[int] = field(default_factory=list)
    description: str = ""
    bbox: Optional[BoundingBox] = None
    zone_id: Optional[str] = None
    first_seen_at: float = 0.0
    confirmed_at: float = 0.0
    last_seen_at: float = 0.0
    resolved_at: Optional[float] = None
    duration_seconds: float = 0.0
    state: IncidentState = IncidentState.CONFIRMED
    snapshot_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "incident_id": self.incident_id,
            "rule_name": self.rule_name,
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "camera_id": self.camera_id,
            "track_id": self.track_id,
            "involved_track_ids": self.involved_track_ids,
            "description": self.description,
            "bbox": self.bbox.as_xyxy() if self.bbox else None,
            "zone_id": self.zone_id,
            "first_seen_at": self.first_seen_at,
            "confirmed_at": self.confirmed_at,
            "last_seen_at": self.last_seen_at,
            "resolved_at": self.resolved_at,
            "duration_seconds": round(self.duration_seconds, 2),
            "state": self.state.value,
            "snapshot_path": self.snapshot_path,
            "metadata": self.metadata,
        }
