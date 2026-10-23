"""
Правило контроля ношения средств индивидуальной защиты (СИЗ / PPE Compliance).
Контролирует обязательное наличие защитной каски (helmet) и сигнального жилета (vest).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from engine.inference.base import Detection
from engine.rules.base import BaseRule, FrameContext, RuleViolation, ViolationSeverity
from engine.tracking.types import TrackedObject


class PPEComplianceRule(BaseRule):
    """
    Контроль ношения СИЗ (каска, жилет) персоналом на производственной площадке.
    """

    def __init__(
        self,
        require_helmet: bool = True,
        require_vest: bool = True,
        helmet_class: str = "helmet",
        no_helmet_class: str = "no_helmet",
        vest_class: str = "vest",
        no_vest_class: str = "no_vest",
        severity: ViolationSeverity = ViolationSeverity.HIGH,
        is_enabled: bool = True,
    ) -> None:
        super().__init__(name="ppe_compliance", is_enabled=is_enabled)
        self.require_helmet = require_helmet
        self.require_vest = require_vest
        self.helmet_class = helmet_class
        self.no_helmet_class = no_helmet_class
        self.vest_class = vest_class
        self.no_vest_class = no_vest_class
        self.severity = severity

    def evaluate(self, tracks: List[TrackedObject], context: FrameContext) -> List[RuleViolation]:
        if not self.is_enabled:
            return []

        persons = [t for t in tracks if t.class_name == "person"]
        if not persons:
            return []

        # Извлекаем все детекции текущего кадра из контекста (если доступны)
        all_detections: List[Detection] = getattr(context, "all_detections", [])

        violations: List[RuleViolation] = []

        for p in persons:
            head_box = p.bbox.head_box
            torso_box = p.bbox.torso_box

            has_helmet = False
            has_explicit_no_helmet = False
            has_vest = False
            has_explicit_no_vest = False

            # Проверяем перекрытие детекций СИЗ с областями тела рабочего
            for det in all_detections:
                if det.class_name == self.helmet_class:
                    if head_box.iou(det.bbox) > 0.05 or det.bbox.iou(head_box) > 0.1:
                        has_helmet = True
                elif det.class_name == self.no_helmet_class:
                    if head_box.iou(det.bbox) > 0.05 or det.bbox.iou(head_box) > 0.1:
                        has_explicit_no_helmet = True

                elif det.class_name == self.vest_class:
                    if torso_box.iou(det.bbox) > 0.05 or det.bbox.iou(torso_box) > 0.1:
                        has_vest = True
                elif det.class_name == self.no_vest_class:
                    if torso_box.iou(det.bbox) > 0.05 or det.bbox.iou(torso_box) > 0.1:
                        has_explicit_no_vest = True

            # Нарушение по каске
            if self.require_helmet and (has_explicit_no_helmet or (not has_helmet and all_detections)):
                desc = f"Нарушение правил ТБ: у сотрудника #{p.track_id} отсутствует защитная каска"
                violations.append(
                    RuleViolation(
                        rule_name=self.name,
                        rule_id=f"PPE_NO_HELMET_{p.track_id}",
                        severity=self.severity,
                        timestamp=context.timestamp,
                        camera_id=context.camera_id,
                        track_id=p.track_id,
                        involved_track_ids=[p.track_id],
                        description=desc,
                        bbox=p.bbox,
                        metadata={"ppe_type": "helmet", "status": "missing"},
                    )
                )

            # Нарушение по жилету
            if self.require_vest and (has_explicit_no_vest or (not has_vest and all_detections)):
                desc = f"Нарушение правил ТБ: у сотрудника #{p.track_id} отсутствует сигнальный жилет"
                violations.append(
                    RuleViolation(
                        rule_name=self.name,
                        rule_id=f"PPE_NO_VEST_{p.track_id}",
                        severity=self.severity,
                        timestamp=context.timestamp,
                        camera_id=context.camera_id,
                        track_id=p.track_id,
                        involved_track_ids=[p.track_id],
                        description=desc,
                        bbox=p.bbox,
                        metadata={"ppe_type": "vest", "status": "missing"},
                    )
                )

        return violations
