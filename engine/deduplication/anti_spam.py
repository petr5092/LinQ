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
    ) -> None:
        self.debounce_frames = debounce_frames
        self.cooldown_seconds = cooldown_seconds
        self.resolve_frames = resolve_frames

        # Кандидаты, ожидающие подтверждения: key -> _ViolationCandidate
        self._candidates: Dict[Tuple[str, str, int], _ViolationCandidate] = {}

        # Активные подтвержденные инциденты: key -> ConfirmedIncident
        self._active_incidents: Dict[Tuple[str, str, int], ConfirmedIncident] = {}

        # Время последнего оповещения для кулдауна: key -> float (timestamp)
        self._last_alert_time: Dict[Tuple[str, str, int], float] = {}

    @staticmethod
    def _make_key(violation: RuleViolation) -> Tuple[str, str, int]:
        return (violation.camera_id, violation.rule_name, violation.track_id)

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
        seen_keys: Set[Tuple[str, str, int]] = set()
        newly_confirmed: List[ConfirmedIncident] = []

        # 1. Обработка поступивших нарушений
        for v in violations:
            key = self._make_key(v)
            seen_keys.add(key)

            # Проверяем, не находится ли инцидент уже в активном состоянии под кулдауном
            if key in self._active_incidents:
                active_inc = self._active_incidents[key]
                active_inc.last_seen_at = now
                active_inc.duration_seconds = max(0.0, now - active_inc.first_seen_at)
                active_inc.bbox = v.bbox
                active_inc.metadata = v.metadata
                # Сбрасываем флаг завершения, если нарушение возобновилось
                if active_inc.state == IncidentState.RESOLVED:
                    active_inc.state = IncidentState.ACTIVE
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
            if cand.streak_count >= self.debounce_frames:
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
            if key not in seen_keys:
                cand.missed_count += 1
                if cand.missed_count >= 5:  # если нарушитель исчез на 5 кадров, сбрасываем кандидат
                    stale_candidates.append(key)

        for key in stale_candidates:
            del self._candidates[key]

        # 3. Обработка активных инцидентов, которые перестали наблюдаться (перевод в RESOLVED)
        resolved_keys = []
        for key, active_inc in self._active_incidents.items():
            if key not in seen_keys:
                # Сколько времени прошло с последнего появления
                time_since_seen = now - active_inc.last_seen_at
                # Если не видно более 2 секунд, фиксируем завершение
                if active_inc.state != IncidentState.RESOLVED and time_since_seen > (self.resolve_frames / context.fps):
                    active_inc.state = IncidentState.RESOLVED
                    active_inc.resolved_at = active_inc.last_seen_at
                    active_inc.duration_seconds = max(0.0, active_inc.last_seen_at - active_inc.first_seen_at)

            # Очистка из памяти после истечения полного кулдауна
            if now - self._last_alert_time.get(key, 0.0) >= self.cooldown_seconds:
                resolved_keys.append(key)

        for key in resolved_keys:
            self._active_incidents.pop(key, None)
            self._last_alert_time.pop(key, None)

        all_active = list(self._active_incidents.values())
        return newly_confirmed, all_active

    def reset(self) -> None:
        """Сброс внутренних состояний дедупликатора."""
        self._candidates.clear()
        self._active_incidents.clear()
        self._last_alert_time.clear()
