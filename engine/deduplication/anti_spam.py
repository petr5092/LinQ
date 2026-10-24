"""
Anti-Spam Engine — Подавление дребезга (Debounce) и дубликатов (Cooldown) по трекам.
Гарантирует отсутствие лавины одинаковых сообщений оператору при длящемся нарушении.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from engine.deduplication.types import ConfirmedIncident, IncidentState
from engine.rules.base import FrameContext, RuleViolation, ViolationSeverity


@dataclass
class _ViolationCandidate:
    """Внутренний кандидат на подтверждение (debounce streak)."""
    violation: RuleViolation
    streak_count: int = 1
    missed_count: int = 0
    first_seen_at: float = 0.0
    last_seen_at: float = 0.0


class AntiSpamEngine:
    """
    Система подавления ложных тревог и дедупликации инцидентов.
    """

    def __init__(
        self,
        debounce_frames: int = 10,       # Количество кадров подтверждения (~0.4-1.0 сек)
        cooldown_seconds: float = 300.0,  # Защитный интервал тишины на один инцидент (5 минут)
        resolve_frames: int = 25,         # Кадров отсутствия нарушения для перевода в RESOLVED (~1.0 сек)
        debounce_seconds: float = 0.0,
    ) -> None:
        if debounce_frames < 1 or resolve_frames < 1 or cooldown_seconds < 0 or debounce_seconds < 0:
            raise ValueError("Debounce/resolve frames must be positive; time intervals must be nonnegative")
        self.debounce_frames = debounce_frames
        self.cooldown_seconds = cooldown_seconds
        self.resolve_frames = resolve_frames
        self.debounce_seconds = debounce_seconds

        # Кандидаты, ожидающие подтверждения: key -> _ViolationCandidate
        self._candidates: Dict[Tuple[str, str, str, int], _ViolationCandidate] = {}

        # Активные подтвержденные инциденты: key -> ConfirmedIncident
        self._active_incidents: Dict[Tuple[str, str, str, int], ConfirmedIncident] = {}

        # Время последнего оповещения для кулдауна: key -> float (timestamp)
        self._last_alert_time: Dict[Tuple[str, str, str, int], float] = {}
        self._missed_frames: Dict[Tuple[str, str, str, int], int] = {}

    @staticmethod
    def _make_key(violation: RuleViolation) -> Tuple[str, str, str, int]:
        return (violation.camera_id, violation.rule_name, violation.rule_id, violation.track_id)

    def process(
        self,
        violations: List[RuleViolation],
        context: FrameContext,
    ) -> Tuple[List[ConfirmedIncident], List[ConfirmedIncident]]:
        """
        Обработка сырых нарушений кадра.
        :param violations: список выявленных правил ТБ нарушений
        :param context: метаданные текущего кадра
        :return: (newly_confirmed, all_active) — только что верифицированные инциденты для мгновенного
                 алерта и список всех текущих активных инцидентов.
        """
        now = context.timestamp
        seen_keys: Set[Tuple[str, str, str, int]] = set()
        newly_confirmed: List[ConfirmedIncident] = []

        # Expire only completed incidents: a continuous violation remains one
        # incident even when it lasts longer than cooldown_seconds.
        for key, incident in list(self._active_incidents.items()):
            if (key[0] == context.camera_id and incident.state == IncidentState.RESOLVED
                    and now - self._last_alert_time[key] >= self.cooldown_seconds):
                self._active_incidents.pop(key)
                self._last_alert_time.pop(key)
                self._missed_frames.pop(key, None)

        # 1. Обработка поступивших нарушений
        for v in violations:
            key = self._make_key(v)
            if key in seen_keys:
                continue  # Multiple detections in one frame are not a streak.
            seen_keys.add(key)
            self._missed_frames.pop(key, None)

            # Проверяем, не находится ли инцидент уже в активном состоянии под кулдауном
            if key in self._active_incidents:
                active_inc = self._active_incidents[key]
                active_inc.last_seen_at = now
                active_inc.duration_seconds = max(0.0, now - active_inc.first_seen_at)
                active_inc.bbox = v.bbox
                active_inc.metadata = dict(v.metadata)
                active_inc.description = v.description
                active_inc.severity = v.severity
                # Сбрасываем флаг завершения, если нарушение возобновилось
                if active_inc.state == IncidentState.RESOLVED:
                    active_inc.state = IncidentState.ACTIVE
                    active_inc.resolved_at = None
                continue

            # Проверяем кулдаун от предыдущего закрытого инцидента по этому же треку
            if key in self._last_alert_time and (now - self._last_alert_time[key]) < self.cooldown_seconds:
                continue

            # Обработка кандидатов (Debounce)
            if key in self._candidates:
                cand = self._candidates[key]
                cand.streak_count += 1
                cand.missed_count = 0
                cand.last_seen_at = now
                cand.violation = v  # обновляем актуальные метаданные
            else:
                # Первый раз увидели нарушение — создаем кандидата
                cand = _ViolationCandidate(
                    violation=v,
                    streak_count=1,
                    missed_count=0,
                    first_seen_at=now,
                    last_seen_at=now,
                )
                self._candidates[key] = cand

            # Проверка достижения порога debounce
            if (cand.streak_count >= self.debounce_frames
                    and now - cand.first_seen_at >= self.debounce_seconds):
                # ПОДТВЕРЖДЕНО: порождаем новый инцидент
                confirmed = ConfirmedIncident(
                    rule_name=v.rule_name,
                    rule_id=v.rule_id,
                    severity=v.severity,
                    camera_id=v.camera_id,
                    track_id=v.track_id,
                    involved_track_ids=list(v.involved_track_ids),
                    description=v.description,
                    bbox=v.bbox,
                    zone_id=v.zone_id,
                    first_seen_at=cand.first_seen_at,
                    confirmed_at=now,
                    last_seen_at=now,
                    duration_seconds=max(0.0, now - cand.first_seen_at),
                    state=IncidentState.CONFIRMED,
                    metadata=dict(v.metadata),
                )

                self._active_incidents[key] = confirmed
                self._last_alert_time[key] = now
                newly_confirmed.append(confirmed)

                # Удаляем из кандидатов
                self._candidates.pop(key, None)

        # 2. Обработка пропущенных кандидатов (сброс дребезга)
        stale_candidates = []
        for key, cand in self._candidates.items():
            if key[0] == context.camera_id and key not in seen_keys:
                stale_candidates.append(key)

        for key in stale_candidates:
            del self._candidates[key]

        # 3. Обработка активных инцидентов, которые перестали наблюдаться (перевод в RESOLVED)
        for key, active_inc in self._active_incidents.items():
            if key[0] == context.camera_id and key not in seen_keys:
                self._missed_frames[key] = self._missed_frames.get(key, 0) + 1
                if active_inc.state != IncidentState.RESOLVED and self._missed_frames[key] >= self.resolve_frames:
                    active_inc.state = IncidentState.RESOLVED
                    active_inc.resolved_at = active_inc.last_seen_at
                    active_inc.duration_seconds = max(0.0, active_inc.last_seen_at - active_inc.first_seen_at)

        all_active = [incident for key, incident in self._active_incidents.items()
                      if key[0] == context.camera_id and incident.state != IncidentState.RESOLVED]
        return newly_confirmed, all_active

    def reset(self) -> None:
        """Сброс внутренних состояний дедупликатора."""
        self._candidates.clear()
        self._active_incidents.clear()
        self._last_alert_time.clear()
        self._missed_frames.clear()
