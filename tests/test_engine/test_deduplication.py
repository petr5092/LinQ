"""
Тесты анти-спама и дедупликации инцидентов (AntiSpamEngine & State Machine) по стандарту test-master.
Покрытие: Debounce, Cooldown, Resolution, Reactivation, Candidate Timeout, Multi-track.
"""

import pytest
from engine.deduplication.anti_spam import AntiSpamEngine
from engine.deduplication.types import ConfirmedIncident, IncidentState
from engine.inference.base import BoundingBox
from engine.rules.base import FrameContext, RuleViolation, ViolationSeverity


def test_debounce_suppresses_flickering():
    """Отсев кратковременных артефактов детекции (длительность меньше debounce_frames)."""
    anti_spam = AntiSpamEngine(debounce_frames=5, cooldown_seconds=60.0)

    raw_violation = RuleViolation(
        rule_name="danger_zone",
        rule_id="DZ_01",
        severity=ViolationSeverity.HIGH,
        timestamp=100.0,
        camera_id="cam_01",
        track_id=42,
    )

    # Кадры 1-4: еще не набран debounce (порог 5)
    for f in range(1, 5):
        ctx = FrameContext(frame_id=f, timestamp=100.0 + f * 0.04)
        newly_confirmed, _ = anti_spam.process([raw_violation], ctx)
        assert len(newly_confirmed) == 0, f"На кадре {f} не должно быть оповещения"

    # Кадр 5: набран порог debounce!
    ctx_5 = FrameContext(frame_id=5, timestamp=100.20)
    newly_confirmed, all_active = anti_spam.process([raw_violation], ctx_5)

    assert len(newly_confirmed) == 1
    assert newly_confirmed[0].track_id == 42
    assert newly_confirmed[0].state == IncidentState.CONFIRMED


def test_candidate_pruning_on_flapping():
    """Если кандидат исчезает до подтверждения (более 5 кадров), он сбрасывается."""
    anti_spam = AntiSpamEngine(debounce_frames=6, cooldown_seconds=60.0)

    raw = RuleViolation("danger_zone", "DZ_01", ViolationSeverity.HIGH, 10.0, "cam_01", 10)

    # Появился на 2 кадра
    anti_spam.process([raw], FrameContext(1, 10.0))
    anti_spam.process([raw], FrameContext(2, 10.04))
    assert len(anti_spam._candidates) == 1

    # Исчез на 6 кадров
    for f in range(3, 9):
        anti_spam.process([], FrameContext(f, 10.0 + f * 0.04))

    # Кандидат должен быть удален из памяти
    assert len(anti_spam._candidates) == 0


def test_cooldown_blocks_spam_alerts():
    """Одно длительное нарушение порождает ровно одно оповещение за весь период кулдауна."""
    anti_spam = AntiSpamEngine(debounce_frames=3, cooldown_seconds=10.0)

    raw_violation = RuleViolation(
        rule_name="danger_zone",
        rule_id="DZ_01",
        severity=ViolationSeverity.HIGH,
        timestamp=100.0,
        camera_id="cam_01",
        track_id=99,
    )

    # Набираем 3 кадра подтверждения
    for f in range(1, 4):
        ctx = FrameContext(frame_id=f, timestamp=100.0 + f * 0.04)
        newly_confirmed, _ = anti_spam.process([raw_violation], ctx)

    assert len(newly_confirmed) == 1

    # Следующие 30 кадров рабочий продолжает нарушать
    for f in range(4, 34):
        ctx = FrameContext(frame_id=f, timestamp=100.0 + f * 0.04)
        more_confirmed, active = anti_spam.process([raw_violation], ctx)
        assert len(more_confirmed) == 0, f"На кадре {f} произошел спам дублем!"
        assert len(active) == 1
        assert active[0].duration_seconds > 0.0


def test_incident_resolution_and_reactivation():
    """Переход в RESOLVED при исчезновении и реактивация в ACTIVE при возобновлении."""
    anti_spam = AntiSpamEngine(debounce_frames=2, cooldown_seconds=60.0, resolve_frames=5)

    raw_violation = RuleViolation(
        rule_name="danger_zone",
        rule_id="DZ_01",
        severity=ViolationSeverity.HIGH,
        timestamp=100.0,
        camera_id="cam_01",
        track_id=12,
    )

    # 1. Подтверждаем инцидент
    anti_spam.process([raw_violation], FrameContext(1, 100.0, fps=25.0))
    newly_confirmed, _ = anti_spam.process([raw_violation], FrameContext(2, 100.04, fps=25.0))
    assert len(newly_confirmed) == 1

    # 2. Нарушитель ушел (6 кадров тишины)
    for f in range(3, 9):
        anti_spam.process([], FrameContext(f, 100.0 + f * 0.1, fps=25.0))

    # Статус RESOLVED
    assert anti_spam._active_incidents[("cam_01", "danger_zone", 12)].state == IncidentState.RESOLVED

    # 3. Нарушитель вернулся во время действия кулдауна (60 сек)
    anti_spam.process([raw_violation], FrameContext(10, 102.0, fps=25.0))
    active_inc = anti_spam._active_incidents[("cam_01", "danger_zone", 12)]
    # Инцидент возобновился в ACTIVE, но новый алерт НЕ отправлен (newly_confirmed = [])
    assert active_inc.state == IncidentState.ACTIVE


def test_anti_spam_multi_track_and_reset():
    """Независимая обработка двух нарушителей и полный сброс состояния."""
    anti_spam = AntiSpamEngine(debounce_frames=1, cooldown_seconds=60.0)

    v1 = RuleViolation("danger_zone", "DZ_01", ViolationSeverity.CRITICAL, 1.0, "cam_1", 1)
    v2 = RuleViolation("danger_zone", "DZ_01", ViolationSeverity.CRITICAL, 1.0, "cam_1", 2)

    new_incidents, active = anti_spam.process([v1, v2], FrameContext(1, 1.0))
    assert len(new_incidents) == 2
    assert len(active) == 2

    # Проверка to_dict на объекте инцидента
    d = new_incidents[0].to_dict()
    assert "incident_id" in d
    assert d["severity"] == "CRITICAL"

    # Сброс (reset)
    anti_spam.reset()
    assert len(anti_spam._active_incidents) == 0
    assert len(anti_spam._candidates) == 0
