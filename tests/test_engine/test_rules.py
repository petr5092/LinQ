"""
Тесты движка правил охраны труда (RulesEngine) по стандарту test-master.
Покрытие: DangerZone, Proximity, FallDetection, PPECompliance, PhoneUsage, RulesEngine.
"""

import pytest
from engine.inference.base import BoundingBox, Detection
from engine.rules.base import FrameContext, RuleViolation, ViolationSeverity
from engine.rules.danger_zone import DangerZoneRule, ZoneDefinition
from engine.rules.engine import RulesEngine
from engine.rules.fall_detection import FallDetectionRule
from engine.rules.phone_usage import PhoneUsageRule
from engine.rules.ppe_compliance import PPEComplianceRule
from engine.rules.proximity import ProximityRule
from engine.rules.registry import build_rules_engine, get_incident_presentation
from engine.tracking.types import TrackedObject


# ==============================================================================
# 1. DangerZoneRule
# ==============================================================================

def test_danger_zone_initialization_and_validation():
    """Проверка валидации полигона (минимум 3 вершины) и управления зонами."""
    with pytest.raises(ValueError):
        ZoneDefinition(zone_id="bad", name="bad", polygon=[(10.0, 10.0), (20.0, 20.0)])

    zone = ZoneDefinition(
        zone_id="zone1",
        name="Zone 1",
        polygon=[(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)],
    )
    rule = DangerZoneRule([zone])
    assert len(rule.zones) == 1

    rule.remove_zone("zone1")
    assert len(rule.zones) == 0

    rule.add_zone(zone)
    rule.clear_zones()
    assert len(rule.zones) == 0


def test_danger_zone_allowed_and_forbidden_classes():
    """Спецтехника (forklift) в зоне разрешена, а человек (person) — нарушитель."""
    zone = ZoneDefinition(
        zone_id="crane",
        name="Зона крана",
        polygon=[(100.0, 100.0), (300.0, 100.0), (300.0, 300.0), (100.0, 300.0)],
        forbidden_classes=["person"],
    )
    rule = DangerZoneRule([zone])
    ctx = FrameContext(1, 100.0)

    person = TrackedObject(1, 0, "person", BoundingBox(150, 150, 200, 250), 0.9)
    forklift = TrackedObject(2, 1, "forklift", BoundingBox(120, 120, 220, 260), 0.9)

    violations = rule.evaluate([person, forklift], ctx)
    assert len(violations) == 1
    assert violations[0].track_id == 1  # Только человек зафиксирован как нарушитель


def test_danger_zone_disabled_and_empty():
    """Тестирование отключенного правила и пустых зон."""
    rule = DangerZoneRule([], is_enabled=False)
    ctx = FrameContext(1, 1.0)
    person = TrackedObject(1, 0, "person", BoundingBox(150, 150, 200, 250), 0.9)
    assert len(rule.evaluate([person], ctx)) == 0

    rule.is_enabled = True
    assert len(rule.evaluate([person], ctx)) == 0


# ==============================================================================
# 2. ProximityRule
# ==============================================================================

def test_proximity_closing_in_escalation():
    """Сближение на встречных курсах повышает строгость нарушения до CRITICAL."""
    rule = ProximityRule(safe_distance_px=100.0)
    ctx = FrameContext(1, 10.0)

    # Человек движется вправо (vx = 2.0)
    worker = TrackedObject(
        track_id=1,
        class_id=0,
        class_name="person",
        bbox=BoundingBox(100.0, 100.0, 140.0, 180.0),
        confidence=0.9,
        velocity=(2.0, 0.0),
        speed=2.0,
    )

    # Погрузчик движется навстречу влево (vx = -3.0), дистанция 60 px
    forklift = TrackedObject(
        track_id=2,
        class_id=1,
        class_name="forklift",
        bbox=BoundingBox(170.0, 100.0, 250.0, 180.0),
        confidence=0.9,
        velocity=(-3.0, 0.0),
        speed=3.0,
    )

    violations = rule.evaluate([worker, forklift], ctx)
    assert len(violations) == 1
    # При быстром сближении строгость эскалируется
    assert violations[0].severity == ViolationSeverity.CRITICAL


def test_proximity_disabled_and_no_target_objects():
    """Проверка отключенного правила и отсутствия взаимодействующих объектов."""
    rule = ProximityRule(safe_distance_px=100.0, is_enabled=False)
    ctx = FrameContext(1, 10.0)
    worker = TrackedObject(1, 0, "person", BoundingBox(100, 100, 140, 180), 0.9)
    assert len(rule.evaluate([worker], ctx)) == 0

    rule.is_enabled = True
    # Только рабочий без погрузчика
    assert len(rule.evaluate([worker], ctx)) == 0


# ==============================================================================
# 3. FallDetectionRule
# ==============================================================================

def test_fall_detection_full_incident_lifecycle():
    """Полный жизненный цикл падения: горизонтальное положение, подтверждение, детекция и очистка трека."""
    rule = FallDetectionRule(aspect_ratio_thresh=1.2, min_frames_lying=2, min_lying_seconds=0.0)
    ctx = FrameContext(1, 1.0)

    # 1. Первый кадр горизонтального положения (ar = 150/60 = 2.5, speed=0.1)
    fallen = TrackedObject(1, 0, "person", BoundingBox(100, 100, 250, 160), 0.9, speed=0.1)
    v1 = rule.evaluate([fallen], ctx)
    assert len(v1) == 0  # 1 кадр < min_frames_lying (2)
    assert rule._lying_frame_count[(ctx.camera_id, 1)] == 1

    # 2. Второй кадр: фиксация падения
    ctx.frame_id = 2
    ctx.timestamp = 1.04
    v2 = rule.evaluate([fallen], ctx)
    assert len(v2) == 1
    assert v2[0].rule_name == "fall_detection"
    assert v2[0].severity == ViolationSeverity.CRITICAL
    assert v2[0].track_id == 1
    assert "FALL_1" in v2[0].rule_id

    # 3. Человек поднялся (ar = 50/150 = 0.33)
    standing = TrackedObject(1, 0, "person", BoundingBox(100, 100, 150, 250), 0.9, speed=1.0)
    v3 = rule.evaluate([standing], ctx)
    assert len(v3) == 0
    assert (ctx.camera_id, 1) not in rule._lying_frame_count

    # 4. Очистка счетчиков пропавших треков
    rule.evaluate([fallen], ctx)
    assert (ctx.camera_id, 1) in rule._lying_frame_count
    # В следующем кадре трек 1 пропал
    rule.evaluate([], ctx)
    assert (ctx.camera_id, 1) not in rule._lying_frame_count


def test_fall_detection_disabled_and_non_target():
    """Тестирование нецелевого класса и отключенного состояния."""
    rule = FallDetectionRule(is_enabled=False)
    ctx = FrameContext(1, 1.0)
    fallen = TrackedObject(1, 0, "person", BoundingBox(100, 100, 250, 160), 0.9, speed=0.1)
    assert len(rule.evaluate([fallen], ctx)) == 0

    rule.is_enabled = True
    vehicle = TrackedObject(2, 1, "forklift", BoundingBox(100, 100, 250, 160), 0.9, speed=0.1)
    assert len(rule.evaluate([vehicle], ctx)) == 0


# ==============================================================================
# 4. PPEComplianceRule
# ==============================================================================

def test_ppe_compliance_full_coverage():
    """Тестирование явных меток отсутствия (no_helmet/no_vest) и полного комплекта СИЗ."""
    rule = PPEComplianceRule(require_helmet=True, require_vest=True)

    person = TrackedObject(1, 0, "person", BoundingBox(100, 100, 160, 280), 0.9)

    # 1. Явная детекция отсутствия каски (no_helmet)
    no_helmet_det = Detection(BoundingBox(110, 100, 150, 140), 0.85, 4, "no_helmet")
    ctx1 = FrameContext(1, 1.0, all_detections=[no_helmet_det])
    v1 = rule.evaluate([person], ctx1)
    assert any(v.metadata.get("ppe_type") == "helmet" for v in v1)

    # 2. Явная детекция отсутствия жилета (no_vest)
    no_vest_det = Detection(BoundingBox(105, 140, 155, 220), 0.85, 6, "no_vest")
    ctx_vest = FrameContext(2, 1.04, all_detections=[no_vest_det])
    v_vest = rule.evaluate([person], ctx_vest)
    assert any(v.metadata.get("ppe_type") == "vest" for v in v_vest)

    # 3. Полный комплект СИЗ: каска + жилет
    helmet_det = Detection(BoundingBox(110, 100, 150, 140), 0.85, 3, "helmet")
    vest_det = Detection(BoundingBox(105, 140, 155, 220), 0.88, 5, "vest")
    ctx2 = FrameContext(3, 1.08, all_detections=[helmet_det, vest_det])
    v2 = rule.evaluate([person], ctx2)
    assert len(v2) == 0

    # 4. Отключение правила
    rule.is_enabled = False
    assert len(rule.evaluate([person], ctx1)) == 0


# ==============================================================================
# 5. PhoneUsageRule
# ==============================================================================

def test_phone_usage_rule_scenarios():
    """Тестирование правила фиксации мобильного телефона: прямое обнаружение, граничные условия."""
    rule = PhoneUsageRule(confidence_threshold=0.6)

    person_box = BoundingBox(100.0, 100.0, 200.0, 300.0)  # w=100, h=200
    person_track = TrackedObject(1, 0, "person", person_box, 0.9)
    forklift_track = TrackedObject(2, 1, "forklift", person_box, 0.9)

    # 1. Телефон в верхней зоне человека (y1 + 0.75*h = 250)
    phone_box = BoundingBox(140.0, 120.0, 160.0, 150.0)
    phone_det = Detection(phone_box, 0.85, 2, "phone")

    ctx = FrameContext(1, 10.0, all_detections=[phone_det])
    violations = rule.evaluate([person_track, forklift_track], ctx)
    assert len(violations) == 1
    assert violations[0].track_id == 1
    assert violations[0].rule_name == "phone_usage"
    assert violations[0].severity == ViolationSeverity.LOW

    # 2. Телефон с низкой уверенностью (0.4 < 0.6)
    low_phone = Detection(phone_box, 0.4, 2, "phone")
    assert len(rule.evaluate([person_track], FrameContext(2, 11.0, all_detections=[low_phone]))) == 0

    # 3. Телефон далеко от человека
    far_phone = Detection(BoundingBox(500.0, 500.0, 520.0, 550.0), 0.9, 2, "phone")
    assert len(rule.evaluate([person_track], FrameContext(3, 12.0, all_detections=[far_phone]))) == 0

    # 4. Вырожденный бокс человека
    bad_person = TrackedObject(3, 0, "person", BoundingBox(100.0, 100.0, 100.0, 100.0), 0.9)
    assert len(rule.evaluate([bad_person], ctx)) == 0

    # 5. Отключенное правило
    rule.is_enabled = False
    assert len(rule.evaluate([person_track], ctx)) == 0


# ==============================================================================
# 6. RulesEngine: управление и отказоустойчивость
# ==============================================================================

def test_rules_engine_orchestration_and_safety():
    """Регистрация, отключение, удаление и обработка исключений в RulesEngine."""
    engine = RulesEngine()
    dz = DangerZoneRule()
    engine.add_rule(dz)
    assert engine.get_rule("danger_zone") is dz

    # Отключение правила
    dz.is_enabled = False
    assert len(engine.evaluate([], FrameContext(1, 1.0))) == 0

    # Очистка всех правил
    engine.clear_rules()
    assert engine.get_rule("danger_zone") is None

    # Добавление правила, выбрасывающего исключение
    class FaultyRule:
        name = "faulty"
        is_enabled = True

        def evaluate(self, tracks, context):
            raise RuntimeError("Engine fault simulation")

    engine.add_rule(FaultyRule())
    # RulesEngine не падает, а логирует ошибку и возвращает доступные нарушения
    violations = engine.evaluate([], FrameContext(2, 2.0))
    assert len(violations) == 0


def test_shared_rule_registry_builds_worker_and_pipeline_defaults():
    """Оба режима используют реестр, сохраняя специфичную настройку worker."""
    zone = ZoneDefinition(
        zone_id="worker_zone",
        name="Зона worker",
        polygon=[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)],
    )

    worker_engine = build_rules_engine(zones=[zone], for_worker=True)
    pipeline_engine = build_rules_engine()

    assert set(worker_engine.rules) == {
        "danger_zone",
        "ppe_compliance",
        "fall_detection",
        "phone_usage",
        "proximity",
    }
    assert set(pipeline_engine.rules) == {
        "danger_zone",
        "ppe_compliance",
        "fall_detection",
        "proximity",
    }
    assert worker_engine.get_rule("danger_zone").zones["worker_zone"] is zone


def test_incident_presentation_comes_from_rule_registry():
    """Правило может получить текст инцидента из реестра или безопасный fallback."""
    helmet = get_incident_presentation("ppe_compliance", {"ppe_type": "helmet"})
    assert helmet.title == "Сотрудник без каски"
    assert helmet.incident_type == "person"

    danger_zone = get_incident_presentation("danger_zone")
    assert danger_zone.title == "Нахождение в опасной зоне"
    assert danger_zone.incident_type == "access"

    custom = get_incident_presentation("new_custom_rule")
    assert custom.title == "New custom rule"
    assert custom.action == "Свяжитесь с мастером смены."
