"""Central registry for built-in safety rules and their incident presentation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from engine.rules.base import BaseRule, ViolationSeverity
from engine.rules.danger_zone import DangerZoneRule, ZoneDefinition
from engine.rules.fall_detection import FallDetectionRule
from engine.rules.phone_usage import PhoneUsageRule
from engine.rules.ppe_compliance import PPEComplianceRule
from engine.rules.proximity import ProximityRule
from engine.rules.engine import RulesEngine


ConfiguredRuleFactory = Callable[[Dict[str, Any], Dict[str, Any], Dict[int, str]], BaseRule]


@dataclass(frozen=True)
class IncidentPresentation:
    title: str
    action: str
    incident_type: str = "person"


@dataclass(frozen=True)
class RuleRegistration:
    factory: Callable[[Optional[List[ZoneDefinition]]], BaseRule]
    presentation: IncidentPresentation
    worker_only: bool = False
    metadata_presentations: Dict[str, IncidentPresentation] = field(default_factory=dict)
    config_factory: Optional[ConfiguredRuleFactory] = None


def _configured_severity(row: Dict[str, Any], default: str = "HIGH") -> ViolationSeverity:
    return ViolationSeverity(str(row.get("severity", default)).upper())


def _build_configured_danger_zone(
    row: Dict[str, Any],
    camera: Dict[str, Any],
    class_names: Dict[int, str],
) -> BaseRule:
    available_classes = set(class_names.values())
    zones = []
    for zone in camera.get("zones", []):
        missing = set(zone.get("forbidden_classes", ["person"])) - available_classes
        if missing:
            raise ValueError(f"Danger zone requires model classes: {sorted(missing)}")
        zone_data = dict(zone)
        zone_data["severity"] = ViolationSeverity(
            str(zone.get("severity", row.get("default_severity", "CRITICAL"))).upper()
        )
        zones.append(ZoneDefinition(**zone_data))
    return DangerZoneRule(zones=zones)


def _build_configured_proximity(
    row: Dict[str, Any],
    _camera: Dict[str, Any],
    class_names: Dict[int, str],
) -> BaseRule:
    available_classes = set(class_names.values())
    vehicles = row.get("vehicle_classes", ["forklift", "truck", "machinery", "car"])
    if "person" not in available_classes or not available_classes.intersection(vehicles):
        raise ValueError("Proximity requires person and a configured vehicle class")
    return ProximityRule(
        safe_distance_px=row.get("safe_distance_px", 140.0),
        vehicle_classes=vehicles,
        severity=_configured_severity(row),
    )


def _build_configured_ppe(
    row: Dict[str, Any],
    _camera: Dict[str, Any],
    class_names: Dict[int, str],
) -> BaseRule:
    required = {"person"}
    if row.get("require_helmet", True):
        required.add("helmet")
    if row.get("require_vest", True):
        required.add("vest")
    missing = required - set(class_names.values())
    if missing:
        raise ValueError(
            f"PPE rule requires model classes: {sorted(missing)}. Disable unsupported rules."
        )
    return PPEComplianceRule(
        require_helmet=row.get("require_helmet", True),
        require_vest=row.get("require_vest", True),
        severity=_configured_severity(row),
    )


def _build_configured_fall_detection(
    row: Dict[str, Any],
    _camera: Dict[str, Any],
    class_names: Dict[int, str],
) -> BaseRule:
    if "person" not in set(class_names.values()):
        raise ValueError("Fall rule requires person class")
    return FallDetectionRule(
        aspect_ratio_thresh=row.get("aspect_ratio_threshold", 1.2),
        max_speed_px=row.get("max_speed_px", 2.0),
        min_frames_lying=row.get("min_frames_lying", 12),
        min_lying_seconds=row.get("min_lying_seconds", 3.0),
        severity=_configured_severity(row, "CRITICAL"),
    )


def _build_configured_phone_usage(
    _row: Dict[str, Any],
    _camera: Dict[str, Any],
    class_names: Dict[int, str],
) -> BaseRule:
    available_classes = set(class_names.values())
    phone_classes = ("phone", "cell phone", "smartphone")
    if "person" not in available_classes or not available_classes.intersection(phone_classes):
        raise ValueError("Phone rule requires person and phone/cell phone/smartphone classes")
    phone_class = next(name for name in phone_classes if name in available_classes)
    return PhoneUsageRule(phone_class_name=phone_class)


RULE_REGISTRY: Dict[str, RuleRegistration] = {
    "danger_zone": RuleRegistration(
        factory=lambda zones: DangerZoneRule(zones=zones),
        presentation=IncidentPresentation(
            "Нахождение в опасной зоне",
            "Подайте звуковой сигнал, покиньте опасную зону.",
            "access",
        ),
        config_factory=_build_configured_danger_zone,
    ),
    "ppe_compliance": RuleRegistration(
        factory=lambda _zones: PPEComplianceRule(require_helmet=True, require_vest=True),
        presentation=IncidentPresentation(
            "Нарушение требований к СИЗ",
            "Остановите работы и проверьте наличие средств индивидуальной защиты.",
        ),
        metadata_presentations={
            "helmet": IncidentPresentation(
                "Сотрудник без каски",
                "Остановите работы, потребуйте надеть защитную каску.",
            ),
            "vest": IncidentPresentation(
                "Сотрудник без жилета",
                "Потребуйте надеть сигнальный жилет.",
            ),
        },
        config_factory=_build_configured_ppe,
    ),
    "fall_detection": RuleRegistration(
        factory=lambda _zones: FallDetectionRule(),
        presentation=IncidentPresentation(
            "Падение человека",
            "Срочно вызовите дежурного медика и остановите технику.",
        ),
        config_factory=_build_configured_fall_detection,
    ),
    "phone_usage": RuleRegistration(
        factory=lambda _zones: PhoneUsageRule(),
        presentation=IncidentPresentation(
            "Использование телефона",
            "Прекратите использование мобильного устройства в рабочей зоне.",
        ),
        worker_only=True,
        config_factory=_build_configured_phone_usage,
    ),
    "proximity": RuleRegistration(
        factory=lambda _zones: ProximityRule(safe_distance_px=140.0),
        presentation=IncidentPresentation(
            "Опасное сближение с техникой",
            "Остановите технику, отойдите на безопасную дистанцию.",
        ),
        config_factory=_build_configured_proximity,
    ),
}


def build_rules_engine(
    zones: Optional[List[ZoneDefinition]] = None,
    *,
    for_worker: bool = False,
) -> RulesEngine:
    """Build a rules engine from the shared registry."""
    engine = RulesEngine()
    for registration in RULE_REGISTRY.values():
        if registration.worker_only and not for_worker:
            continue
        engine.add_rule(registration.factory(zones))
    return engine


def build_configured_rules_engine(
    config: Dict[str, Any],
    camera: Dict[str, Any],
    class_names: Dict[int, str],
) -> RulesEngine:
    """Build enabled, model-validated rules using the shared registry."""
    configured_rules = config.get("rules", {})
    engine = RulesEngine()
    for name, registration in RULE_REGISTRY.items():
        row = configured_rules.get(name, {})
        if not row.get("enabled", False):
            continue
        if registration.config_factory is None:
            engine.add_rule(registration.factory(camera.get("zones")))
        else:
            engine.add_rule(registration.config_factory(row, camera, class_names))
    return engine


def get_incident_presentation(
    rule_name: str,
    metadata: Optional[Dict[str, object]] = None,
) -> IncidentPresentation:
    """Return configured incident text, with a readable fallback for new rules."""
    registration = RULE_REGISTRY.get(rule_name)
    if registration is None:
        title = rule_name.replace("_", " ").strip().capitalize() or "Нарушение требований ТБ"
        return IncidentPresentation(title, "Свяжитесь с мастером смены.")

    incident_metadata = metadata or {}
    metadata_key = incident_metadata.get("ppe_type")
    if isinstance(metadata_key, str):
        return registration.metadata_presentations.get(metadata_key, registration.presentation)
    return registration.presentation
