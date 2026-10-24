"""
Правило детекции падения и длительной неподвижности человека (Fall & Immobility Detection).
Анализирует соотношение сторон bounding box (w / h > 1.2) и вектор скорости трека.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from engine.rules.base import BaseRule, FrameContext, RuleViolation, ViolationSeverity
from engine.tracking.types import TrackedObject


class FallDetectionRule(BaseRule):
    """
    Фиксация падения сотрудника и отсутствия признаков движения на производстве.
    """

    def __init__(
        self,
        aspect_ratio_thresh: float = 1.2,
        max_speed_px: float = 2.0,          # низкая скорость (человек лежит неподвижно)
        min_frames_lying: int = 10,         # минимум кадров в горизонтальном положении
        target_classes: Optional[List[str]] = None,
        severity: ViolationSeverity = ViolationSeverity.CRITICAL,
        is_enabled: bool = True,
        min_lying_seconds: float = 3.0,
    ) -> None:
        super().__init__(name="fall_detection", is_enabled=is_enabled)
        self.aspect_ratio_thresh = aspect_ratio_thresh
        self.max_speed_px = max_speed_px
        self.min_frames_lying = min_frames_lying
        self.target_classes = target_classes or ["person"]
        self.severity = severity
        if min_frames_lying < 1 or min_lying_seconds < 0:
            raise ValueError("Fall confirmation requires positive frames and nonnegative duration")
        self.min_lying_seconds = min_lying_seconds

        # Внутренний счетчик кадров в лежачем положении по track_id
        self._lying_frame_count: Dict[Tuple[str, int], int] = {}
        self._lying_since: Dict[Tuple[str, int], float] = {}

    def reset(self) -> None:
        self._lying_frame_count.clear()
        self._lying_since.clear()

    def evaluate(self, tracks: List[TrackedObject], context: FrameContext) -> List[RuleViolation]:
        if not self.is_enabled:
            return []

        active_track_ids = set()
        violations: List[RuleViolation] = []

        for track in tracks:
            if track.class_name not in self.target_classes or track.time_since_update != 0:
                continue

            key = (context.camera_id, track.track_id)
            active_track_ids.add(key)
            ar = track.aspect_ratio
            speed = track.speed

            # Условие падения: горизонтальная ориентация рамки и отсутствие быстрого движения
            is_lying = (ar >= self.aspect_ratio_thresh) and (speed <= self.max_speed_px)

            if is_lying:
                count = self._lying_frame_count.get(key, 0) + 1
                self._lying_frame_count[key] = count
                self._lying_since.setdefault(key, context.timestamp)
                duration = max(0.0, context.timestamp - self._lying_since[key])

                if count >= self.min_frames_lying and duration >= self.min_lying_seconds:
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
                            "lying_seconds": round(duration, 3),
                        },
                    )
                    violations.append(violation)
            else:
                # Если человек поднялся или двигается вертикально, сбрасываем счетчик
                self._lying_frame_count.pop(key, None)
                self._lying_since.pop(key, None)

        # Очистка счетчиков удаленных треков
        dead_ids = [tid for tid in self._lying_frame_count
                    if tid[0] == context.camera_id and tid not in active_track_ids]
        for tid in dead_ids:
            self._lying_frame_count.pop(tid, None)
            self._lying_since.pop(tid, None)

        return violations
