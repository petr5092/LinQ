"""Central registry for built-in safety rules and their incident presentation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from engine.rules.base import BaseRule
from engine.rules.danger_zone import DangerZoneRule, ZoneDefinition
from engine.rules.fall_detection import FallDetectionRule
from engine.rules.phone_usage import PhoneUsageRule
from engine.rules.ppe_compliance import PPEComplianceRule
from engine.rules.proximity import ProximityRule
from engine.rules.engine import RulesEngine


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


RULE_REGISTRY: Dict[str, RuleRegistration] = {
    "danger_zone": RuleRegistration(
        factory=lambda zones: DangerZoneRule(zones=zones),
        presentation=IncidentPresentation(
            "Нахождение в опасной зоне",
            "Подайте звуковой сигнал, покиньте опасную зону.",
            "access",
        ),
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
    ),
    "fall_detection": RuleRegistration(
        factory=lambda _zones: FallDetectionRule(),
        presentation=IncidentPresentation(
            "Падение человека",
            "Срочно вызовите дежурного медика и остановите технику.",
        ),
    ),
    "phone_usage": RuleRegistration(
        factory=lambda _zones: PhoneUsageRule(),
        presentation=IncidentPresentation(
            "Использование телефона",
            "Прекратите использование мобильного устройства в рабочей зоне.",
        ),
        worker_only=True,
    ),
    "proximity": RuleRegistration(
        factory=lambda _zones: ProximityRule(),
        presentation=IncidentPresentation(
            "Опасное сближение с техникой",
            "Остановите технику, отойдите на безопасную дистанцию.",
        ),
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
