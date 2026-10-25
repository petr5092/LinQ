"""
Правило контроля ношения средств индивидуальной защиты (СИЗ / PPE Compliance).
Контролирует обязательное наличие защитной каски (helmet) и сигнального жилета (vest).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from engine.inference.base import Detection
from engine.rules.base import BaseRule, FrameContext, RuleViolation, ViolationSeverity
from engine.tracking.types import TrackedObject


DEFAULT_HELMET_CLASSES = ("helmet", "hardhat")
DEFAULT_NO_HELMET_CLASSES = ("no_helmet", "no-hardhat", "no_hardhat", "no-helmet")
DEFAULT_VEST_CLASSES = ("vest", "safety vest", "safety_vest")
DEFAULT_NO_VEST_CLASSES = ("no_vest", "no-safety vest", "no_safety_vest", "no-vest")


class PPEComplianceRule(BaseRule):
    """
    Контроль ношения СИЗ (каска, жилет) персоналом на производственной площадке.
    Поддерживает как двухэтапный анализ (человек -> зоны головы/торса -> наличие/отсутствие СИЗ),
    так и прямое распознавание классов отсутствия СИЗ (no_helmet, no_vest).
    """

    def __init__(
        self,
        require_helmet: bool = True,
        require_vest: bool = True,
        helmet_class: Any = DEFAULT_HELMET_CLASSES,
        no_helmet_class: Any = DEFAULT_NO_HELMET_CLASSES,
        vest_class: Any = DEFAULT_VEST_CLASSES,
        no_vest_class: Any = DEFAULT_NO_VEST_CLASSES,
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

        all_detections: List[Detection] = getattr(context, "all_detections", [])
        violations: List[RuleViolation] = []
        covered_tracks: set[int] = set()

        # 1. Анализ через треки людей (person)
        persons = [t for t in tracks if t.class_name == "person"]
        for p in persons:
            head_box = p.bbox.head_box
            torso_box = p.bbox.torso_box

            has_helmet = False
            has_explicit_no_helmet = False
            has_vest = False
            has_explicit_no_vest = False

            # Проверяем перекрытие детекций СИЗ с областями тела рабочего
            for det in all_detections:
                inter_w = max(0.0, min(head_box.x2, det.bbox.x2) - max(head_box.x1, det.bbox.x1))
                inter_h = max(0.0, min(head_box.y2, det.bbox.y2) - max(head_box.y1, det.bbox.y1))
                head_inter_area = inter_w * inter_h
                head_overlap = (head_inter_area / max(det.bbox.area, 1.0)) > 0.15 or head_box.iou(det.bbox) > 0.05

                torso_w = max(0.0, min(torso_box.x2, det.bbox.x2) - max(torso_box.x1, det.bbox.x1))
                torso_h = max(0.0, min(torso_box.y2, det.bbox.y2) - max(torso_box.y1, det.bbox.y1))
                torso_inter_area = torso_w * torso_h
                torso_overlap = (torso_inter_area / max(det.bbox.area, 1.0)) > 0.15 or torso_box.iou(det.bbox) > 0.05

                is_helmet = (det.class_name == self.helmet_class) or (isinstance(self.helmet_class, (set, list, tuple)) and det.class_name in self.helmet_class)
                is_no_helmet = (det.class_name == self.no_helmet_class) or (isinstance(self.no_helmet_class, (set, list, tuple)) and det.class_name in self.no_helmet_class)
                is_vest = (det.class_name == self.vest_class) or (isinstance(self.vest_class, (set, list, tuple)) and det.class_name in self.vest_class)
                is_no_vest = (det.class_name == self.no_vest_class) or (isinstance(self.no_vest_class, (set, list, tuple)) and det.class_name in self.no_vest_class)

                if is_helmet and head_overlap:
                    has_helmet = True
                elif is_no_helmet and head_overlap:
                    has_explicit_no_helmet = True
                elif is_vest and torso_overlap:
                    has_vest = True
                elif is_no_vest and torso_overlap:
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
                covered_tracks.add(p.track_id)

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
                covered_tracks.add(p.track_id)

        # 2. Прямые треки отсутствия СИЗ (когда нейросеть напрямую трекает no_helmet или no_vest)
        for t in tracks:
            if t.track_id in covered_tracks:
                continue

            is_track_no_helmet = (t.class_name == self.no_helmet_class) or (isinstance(self.no_helmet_class, (set, list, tuple)) and t.class_name in self.no_helmet_class)
            is_track_no_vest = (t.class_name == self.no_vest_class) or (isinstance(self.no_vest_class, (set, list, tuple)) and t.class_name in self.no_vest_class)

            if self.require_helmet and is_track_no_helmet:
                violations.append(
                    RuleViolation(
                        rule_name=self.name,
                        rule_id=f"PPE_NO_HELMET_TRACK_{t.track_id}",
                        severity=self.severity,
                        timestamp=context.timestamp,
                        camera_id=context.camera_id,
                        track_id=t.track_id,
                        involved_track_ids=[t.track_id],
                        description=f"Нарушение правил ТБ: обнаружен сотрудник #{t.track_id} без защитной каски",
                        bbox=t.bbox,
                        metadata={"ppe_type": "helmet", "status": "missing"},
                    )
                )
            elif self.require_vest and is_track_no_vest:
                violations.append(
                    RuleViolation(
                        rule_name=self.name,
                        rule_id=f"PPE_NO_VEST_TRACK_{t.track_id}",
                        severity=self.severity,
                        timestamp=context.timestamp,
                        camera_id=context.camera_id,
                        track_id=t.track_id,
                        involved_track_ids=[t.track_id],
                        description=f"Нарушение правил ТБ: обнаружен сотрудник #{t.track_id} без сигнального жилета",
                        bbox=t.bbox,
                        metadata={"ppe_type": "vest", "status": "missing"},
                    )
                )

        return violations
