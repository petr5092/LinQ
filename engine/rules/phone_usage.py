"""
Правило контроля использования мобильного телефона в рабочей зоне.
Нахождение смартфона в руках или возле головы рабочего во время движения/работы
является нарушением ТБ (отвлечение внимания, риск травматизма).
"""

from __future__ import annotations

from typing import List, Optional
from engine.inference.base import BoundingBox, Detection
from engine.rules.base import BaseRule, FrameContext, RuleViolation, ViolationSeverity
from engine.tracking.types import TrackedObject


class PhoneUsageRule(BaseRule):
    """
    Правило фиксации использования телефона рабочим.
    """

    def __init__(
        self,
        name: str = "phone_usage",
        severity: ViolationSeverity = ViolationSeverity.LOW,
        confidence_threshold: float = 0.50,
        phone_class_name: str = "phone",
        person_class_name: str = "person",
        is_enabled: bool = True,
    ) -> None:
        super().__init__(name=name, is_enabled=is_enabled)
        self.severity = severity
        self.confidence_threshold = confidence_threshold
        self.phone_class_name = phone_class_name
        self.person_class_name = person_class_name

    def evaluate(self, tracks: List[TrackedObject], context: FrameContext) -> List[RuleViolation]:
        violations: List[RuleViolation] = []
        if not self.is_enabled:
            return violations

        # 1. Извлекаем детекции телефонов с достаточной уверенностью
        phone_dets = [
            d for d in context.all_detections
            if hasattr(d, "class_name") and d.class_name == self.phone_class_name and d.confidence >= self.confidence_threshold
        ]

        if not phone_dets:
            return violations

        # 2. Проверяем каждого сопровождаемого человека
        for track in tracks:
            if track.class_name != self.person_class_name:
                continue

            tb = track.bbox
            w, h = tb.width, tb.height
            if h <= 0 or w <= 0:
                continue

            # Область рук/головы/торса человека, где может находиться телефон
            upper_region = BoundingBox(
                x1=tb.x1 - 0.15 * w,
                y1=tb.y1,
                x2=tb.x2 + 0.15 * w,
                y2=tb.y1 + 0.75 * h,
            )

            # Проверяем пересечение с любым обнаруженным телефоном
            for phone in phone_dets:
                pc_x, pc_y = phone.bbox.center
                if (upper_region.x1 <= pc_x <= upper_region.x2 and
                        upper_region.y1 <= pc_y <= upper_region.y2):

                    v = RuleViolation(
                        rule_name=self.name,
                        rule_id="RULE_PHONE_01",
                        severity=self.severity,
                        timestamp=context.timestamp,
                        camera_id=context.camera_id,
                        track_id=track.track_id,
                        involved_track_ids=[track.track_id],
                        description=f"Использование мобильного телефона рабочим #{track.track_id} в рабочей зоне",
                        bbox=track.bbox,
                        metadata={
                            "phone_bbox": list(phone.bbox.as_xyxy()),
                            "phone_confidence": round(phone.confidence, 3),
                        },
                    )
                    violations.append(v)
                    break

        return violations
