"""
Тесты движка правил охраны труда и промышленной безопасности.
"""

import pytest
from engine.inference.base import BoundingBox, Detection
from engine.rules.base import FrameContext, ViolationSeverity
from engine.rules.danger_zone import DangerZoneRule, ZoneDefinition
from engine.rules.engine import RulesEngine
from engine.rules.fall_detection import FallDetectionRule
from engine.rules.ppe_compliance import PPEComplianceRule
from engine.rules.proximity import ProximityRule
from engine.tracking.types import TrackedObject


def test_danger_zone_point_in_polygon():
    zone = ZoneDefinition(
        zone_id="crane_zone",
        name="Опасная зона крана",
        polygon=[(100.0, 100.0), (300.0, 100.0), (300.0, 300.0), (100.0, 300.0)],
        severity=ViolationSeverity.CRITICAL,
        forbidden_classes=["person"],
    )

    rule = DangerZoneRule(zones=[zone])
    context = FrameContext(frame_id=1, timestamp=1000.0, camera_id="cam_01")

    # Рабочий внутри зоны: стопы на (200, 250)
    worker_inside = TrackedObject(
        track_id=101,
        class_id=0,
        class_name="person",
        bbox=BoundingBox(180.0, 150.0, 220.0, 250.0),
        confidence=0.9,
    )

    # Рабочий вне зоны: стопы на (400, 400)
    worker_outside = TrackedObject(
        track_id=102,
        class_id=0,
        class_name="person",
        bbox=BoundingBox(380.0, 300.0, 420.0, 400.0),
        confidence=0.9,
    )

    violations = rule.evaluate([worker_inside, worker_outside], context)
    assert len(violations) == 1
    assert violations[0].track_id == 101
    assert violations[0].zone_id == "crane_zone"
    assert violations[0].severity == ViolationSeverity.CRITICAL


def test_proximity_rule_worker_and_forklift():
    rule = ProximityRule(safe_distance_px=100.0)
    context = FrameContext(frame_id=1, timestamp=1000.0)

    # Рабочий: стопы на (150, 150)
    worker = TrackedObject(
        track_id=1,
        class_id=0,
        class_name="person",
        bbox=BoundingBox(140.0, 100.0, 160.0, 150.0),
        confidence=0.9,
    )

    # Погрузчик близко: стопы на (180, 150) -> расстояние 30 px < 100 px!
    forklift_close = TrackedObject(
        track_id=2,
        class_id=1,
        class_name="forklift",
        bbox=BoundingBox(160.0, 100.0, 200.0, 150.0),
        confidence=0.95,
    )

    violations = rule.evaluate([worker, forklift_close], context)
    assert len(violations) == 1
    assert violations[0].track_id == 1
    assert 2 in violations[0].involved_track_ids


def test_fall_detection_rule():
    rule = FallDetectionRule(
        aspect_ratio_thresh=1.2,
        max_speed_px=1.5,
        min_frames_lying=3,
    )
    context = FrameContext(frame_id=1, timestamp=1000.0)

    # Лежащий неподвижный человек: w=150, h=60 (ar = 2.5 > 1.2), скорость = 0.2
    fallen_worker = TrackedObject(
        track_id=7,
        class_id=0,
        class_name="person",
        bbox=BoundingBox(100.0, 200.0, 250.0, 260.0),
        confidence=0.88,
        speed=0.2,
    )

    # Кадр 1: еще не набрал min_frames_lying (3)
    v1 = rule.evaluate([fallen_worker], context)
    assert len(v1) == 0

    # Кадр 2:
    v2 = rule.evaluate([fallen_worker], context)
    assert len(v2) == 0

    # Кадр 3: сработал порог!
    v3 = rule.evaluate([fallen_worker], context)
    assert len(v3) == 1
    assert v3[0].rule_name == "fall_detection"
    assert v3[0].severity == ViolationSeverity.CRITICAL


def test_ppe_compliance_rule():
    rule = PPEComplianceRule(require_helmet=True, require_vest=True)

    # Человек
    person = TrackedObject(
        track_id=5,
        class_id=0,
        class_name="person",
        bbox=BoundingBox(100.0, 100.0, 160.0, 280.0),
        confidence=0.9,
    )

    # Детекция каски в области головы
    helmet_det = Detection(
        bbox=BoundingBox(110.0, 100.0, 150.0, 140.0),
        confidence=0.85,
        class_id=3,
        class_name="helmet",
    )

    # Контекст без жилета, но с каской
    context = FrameContext(
        frame_id=1,
        timestamp=1000.0,
        all_detections=[helmet_det],
    )

    violations = rule.evaluate([person], context)
    # Должно быть нарушение только по отсутствию жилета
    assert len(violations) == 1
    assert violations[0].metadata["ppe_type"] == "vest"
