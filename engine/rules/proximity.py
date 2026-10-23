"""
Правило опасного сближения человека с подвижной техникой (Proximity Rule).
Контролирует дистанцию между рабочими (person) и спецтехникой (forklift/machinery).
"""

from __future__ import annotations

import math
from typing import List, Optional
from engine.rules.base import BaseRule, FrameContext, RuleViolation, ViolationSeverity
from engine.tracking.types import TrackedObject


class ProximityRule(BaseRule):
    """
    Контроль критической дистанции между пешеходами и транспортом в производственном цехе.
    """

    def __init__(
        self,
        safe_distance_px: float = 120.0,
        person_classes: Optional[List[str]] = None,
        vehicle_classes: Optional[List[str]] = None,
        severity: ViolationSeverity = ViolationSeverity.HIGH,
        is_enabled: bool = True,
    ) -> None:
        super().__init__(name="proximity", is_enabled=is_enabled)
        self.safe_distance_px = safe_distance_px
        self.person_classes = person_classes or ["person"]
        self.vehicle_classes = vehicle_classes or ["forklift", "truck", "machinery", "car"]
        self.severity = severity

    def evaluate(self, tracks: List[TrackedObject], context: FrameContext) -> List[RuleViolation]:
        if not self.is_enabled:
            return []

        persons = [t for t in tracks if t.class_name in self.person_classes]
        vehicles = [t for t in tracks if t.class_name in self.vehicle_classes]

        if not persons or not vehicles:
            return []

        violations: List[RuleViolation] = []

        for p in persons:
            px, py = p.bottom_center
            for v in vehicles:
                vx, vy = v.bottom_center

                # Евклидово расстояние между опорными точками
                dist = math.hypot(px - vx, py - vy)

                if dist < self.safe_distance_px:
                    # Оценка сближения на основе векторов скоростей
                    rel_vx = p.velocity[0] - v.velocity[0]
                    rel_vy = p.velocity[1] - v.velocity[1]
                    is_closing_in = (px - vx) * rel_vx + (py - vy) * rel_vy < 0

                    current_severity = (
                        ViolationSeverity.CRITICAL
                        if (dist < self.safe_distance_px * 0.5 or (is_closing_in and v.speed > 2.0))
                        else self.severity
                    )

                    desc = (
                        f"Опасное сближение: рабочий #{p.track_id} и техника {v.class_name} #{v.track_id} "
                        f"(дистанция {dist:.1f} px при безопасной {self.safe_distance_px:.1f} px)"
                    )

                    violation = RuleViolation(
                        rule_name=self.name,
                        rule_id=f"PROX_{p.track_id}_{v.track_id}",
                        severity=current_severity,
                        timestamp=context.timestamp,
                        camera_id=context.camera_id,
                        track_id=p.track_id,
                        involved_track_ids=[p.track_id, v.track_id],
                        description=desc,
                        bbox=p.bbox,
                        metadata={
                            "distance_px": round(dist, 1),
                            "safe_distance_px": self.safe_distance_px,
                            "person_speed": round(p.speed, 2),
                            "vehicle_speed": round(v.speed, 2),
                            "is_closing_in": is_closing_in,
                        },
                    )
                    violations.append(violation)

        return violations
