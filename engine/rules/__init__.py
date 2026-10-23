"""
Пакет движка правил охраны труда и техники безопасности LinQ Safety Guard.
"""

from engine.rules.base import BaseRule, FrameContext, RuleViolation, ViolationSeverity
from engine.rules.danger_zone import DangerZoneRule, ZoneDefinition
from engine.rules.engine import RulesEngine
from engine.rules.fall_detection import FallDetectionRule
from engine.rules.ppe_compliance import PPEComplianceRule
from engine.rules.proximity import ProximityRule

__all__ = [
    "BaseRule",
    "FrameContext",
    "RuleViolation",
    "ViolationSeverity",
    "DangerZoneRule",
    "ZoneDefinition",
    "RulesEngine",
    "FallDetectionRule",
    "PPEComplianceRule",
    "ProximityRule",
]
