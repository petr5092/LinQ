"""
Правило детекции падения и длительной неподвижности человека (Fall & Immobility Detection).
Анализирует соотношение сторон bounding box (w / h > 1.2) и вектор скорости трека.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from engine.rules.base import BaseRule, FrameContext, RuleViolation, ViolationSeverity
from engine.tracking.types import TrackedObject


class FallDetectionRule(BaseRule):
    """
    Фиксация падения сотрудника и отсутствия признаков движения на производстве.
    """

    def __init__(
        self,
        aspect_ratio_thresh: float = 1.15,  # w / h > 1.15 означает горизонтальное положение
        max_speed_px: float = 2.0,          # низкая скорость (человек лежит неподвижно)
        min_frames_lying: int = 10,         # минимум кадров в горизонтальном положении
        target_classes: Optional[List[str]] = None,
        severity: ViolationSeverity = ViolationSeverity.CRITICAL,
        is_enabled: bool = True,
    ) -> None:
        super().__init__(name="fall_detection", is_enabled=is_enabled)
        self.aspect_ratio_thresh = aspect_ratio_thresh
        self.max_speed_px = max_speed_px
        self.min_frames_lying = min_frames_lying
        self.target_classes = target_classes or ["person"]
        self.severity = severity

        # Внутренний счетчик кадров в лежачем положении по track_id
        self._lying_frame_count: Dict[int, int] = {}

    def evaluate(self, tracks: List[TrackedObject], context: FrameContext) -> List[RuleViolation]:
        if not self.is_enabled:
            return []

        active_track_ids = set()
        violations: List[RuleViolation] = []

        for track in tracks:
            if track.class_name not in self.target_classes:
                continue

            active_track_ids.add(track.track_id)
            ar = track.aspect_ratio
            speed = track.speed

            # Условие падения: горизонтальная ориентация рамки и отсутствие быстрого движения
            is_lying = (ar >= self.aspect_ratio_thresh) and (speed <= self.max_speed_px)

            if is_lying:
                count = self._lying_frame_count.get(track.track_id, 0) + 1
                self._lying_frame_count[track.track_id] = count

                if count >= self.min_frames_lying:
                    desc = (
                        f"Обнаружено падение человека: рабочий #{track.track_id} лежит неподвижно "
                        f"(соотношение w/h = {ar:.2f}, скорость = {speed:.1f} px/кадр, длительность {count} кадров)"
                    )

                    violation = RuleViolation(
                        rule_name=self.name,
                        rule_id=f"FALL_{track.track_id}",
                        severity=self.severity,
                        timestamp=context.timestamp,
                        camera_id=context.camera_id,
                        track_id=track.track_id,
                        involved_track_ids=[track.track_id],
                        description=desc,
                        bbox=track.bbox,
                        metadata={
                            "aspect_ratio": round(ar, 2),
                            "speed": round(speed, 2),
                            "lying_frames": count,
                        },
                    )
                    violations.append(violation)
            else:
                # Если человек поднялся или двигается вертикально, сбрасываем счетчик
                self._lying_frame_count.pop(track.track_id, None)

        # Очистка счетчиков удаленных треков
        dead_ids = [tid for tid in self._lying_frame_count if tid not in active_track_ids]
        for tid in dead_ids:
            self._lying_frame_count.pop(tid, None)

        return violations
