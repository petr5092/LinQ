"""
Тесты дедупликации и подавления ложных тревог (Anti-Spam).
"""

import pytest
from engine.deduplication.anti_spam import AntiSpamEngine
from engine.deduplication.types import IncidentState
from engine.rules.base import FrameContext, RuleViolation, ViolationSeverity


def test_debounce_suppresses_flickering():
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


def test_cooldown_blocks_spam_alerts():
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

    # На 3-м кадре алерт создан
    assert len(newly_confirmed) == 1

    # Следующие 50 кадров рабочий продолжает стоять в зоне
    # Anti-Spam обязан подавить лавину дубликатов!
    for f in range(4, 54):
        ctx = FrameContext(frame_id=f, timestamp=100.0 + f * 0.04)
        more_confirmed, active = anti_spam.process([raw_violation], ctx)
        assert len(more_confirmed) == 0, f"На кадре {f} произошел спам дублем!"
        assert len(active) == 1
        assert active[0].duration_seconds > 0.0


def test_incident_resolution_when_violation_ends():
    anti_spam = AntiSpamEngine(debounce_frames=2, cooldown_seconds=60.0, resolve_frames=5)

    raw_violation = RuleViolation(
        rule_name="danger_zone",
        rule_id="DZ_01",
        severity=ViolationSeverity.HIGH,
        timestamp=100.0,
        camera_id="cam_01",
        track_id=12,
    )

    # 1. Подтверждаем инцидент за 2 кадра
    ctx_1 = FrameContext(frame_id=1, timestamp=100.0, fps=25.0)
    ctx_2 = FrameContext(frame_id=2, timestamp=100.04, fps=25.0)
    anti_spam.process([raw_violation], ctx_1)
    newly_confirmed, _ = anti_spam.process([raw_violation], ctx_2)
    assert len(newly_confirmed) == 1

    # 2. Нарушение прекратилось (пустой список нарушений) на 10 кадров
    for f in range(3, 15):
        ctx_empty = FrameContext(frame_id=f, timestamp=100.0 + f * 0.1, fps=25.0)
        _, active = anti_spam.process([], ctx_empty)

    # Инцидент должен перейти в RESOLVED
    assert len(active) == 1
    assert active[0].state == IncidentState.RESOLVED
    assert active[0].resolved_at is not None
