"""
Правило опасных зон (Danger Zone / Perimeter Intrusion) на базе Shapely.
Контролирует нахождение людей в запрещенных полигональных зонах (Point-in-Polygon).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from shapely.geometry import Point, Polygon

from engine.rules.base import BaseRule, FrameContext, RuleViolation, ViolationSeverity
from engine.tracking.types import TrackedObject


@dataclass
class ZoneDefinition:
    """
    Описание опасной/ограниченной зоны на кадре камеры.
    """
    zone_id: str
    name: str
    polygon: List[Tuple[float, float]]  # список вершин [(x1, y1), (x2, y2), ...]
    severity: ViolationSeverity = ViolationSeverity.CRITICAL
    allowed_classes: List[str] = field(default_factory=list)  # например, ["forklift"]
    forbidden_classes: List[str] = field(default_factory=lambda: ["person"])
    description: str = ""

    def __post_init__(self) -> None:
        if len(self.polygon) < 3:
            raise ValueError(f"Зона {self.zone_id} должна содержать минимум 3 вершины.")
        self._shapely_polygon = Polygon(self.polygon)

    @property
    def shapely_poly(self) -> Polygon:
        return self._shapely_polygon

    def contains_point(self, point_xy: Tuple[float, float]) -> bool:
        pt = Point(point_xy[0], point_xy[1])
        return bool(self._shapely_polygon.contains(pt))


class DangerZoneRule(BaseRule):
    """
    Правило контроля пересечения периметра и опасных зон.
    Проверяет координаты стоп рабочего (bottom_center) относительно полигона зоны.
    """

    def __init__(
        self,
        zones: Optional[List[ZoneDefinition]] = None,
        is_enabled: bool = True,
    ) -> None:
        super().__init__(name="danger_zone", is_enabled=is_enabled)
        self.zones: Dict[str, ZoneDefinition] = {}
        if zones:
            for z in zones:
                self.add_zone(z)

    def add_zone(self, zone: ZoneDefinition) -> None:
        self.zones[zone.zone_id] = zone

    def remove_zone(self, zone_id: str) -> None:
        self.zones.pop(zone_id, None)

    def clear_zones(self) -> None:
        self.zones.clear()

    def evaluate(self, tracks: List[TrackedObject], context: FrameContext) -> List[RuleViolation]:
        if not self.is_enabled or not self.zones:
            return []

        violations: List[RuleViolation] = []

        for track in tracks:
            # Опорная точка человека: стопы (bottom_center рамки)
            foot_point = track.bottom_center

            for zone_id, zone in self.zones.items():
                # Проверяем, запрещен ли класс данного объекта в зоне
                if track.class_name not in zone.forbidden_classes:
                    continue

                if zone.contains_point(foot_point):
                    desc = (
                        f"Нарушение опасной зоны «{zone.name}» (ID: {zone.zone_id}): "
                        f"объект {track.class_name} #{track.track_id} находится внутри периметра"
                    )

                    violation = RuleViolation(
                        rule_name=self.name,
                        rule_id=f"DZ_{zone.zone_id}",
                        severity=zone.severity,
                        timestamp=context.timestamp,
                        camera_id=context.camera_id,
                        track_id=track.track_id,
                        involved_track_ids=[track.track_id],
                        description=desc,
                        bbox=track.bbox,
                        zone_id=zone.zone_id,
                        metadata={
                            "foot_x": round(foot_point[0], 1),
                            "foot_y": round(foot_point[1], 1),
                            "zone_name": zone.name,
                            "speed": round(track.speed, 2),
                        },
                    )
                    violations.append(violation)

        return violations
