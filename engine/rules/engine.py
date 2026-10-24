"""
Оркестратор правил безопасности (RulesEngine).
Выполняет последовательную оценку всех зарегистрированных правил над сопровождаемыми треками.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from engine.rules.base import BaseRule, FrameContext, RuleViolation
from engine.tracking.types import TrackedObject, TrackState


class RulesEngine:
    """
    Реестр и диспетчер правил охраны труда и промышленной безопасности.
    """

    def __init__(self, rules: Optional[List[BaseRule]] = None) -> None:
        self.rules: Dict[str, BaseRule] = {}
        if rules:
            for rule in rules:
                self.add_rule(rule)

    def add_rule(self, rule: BaseRule) -> None:
        self.rules[rule.name] = rule

    def remove_rule(self, rule_name: str) -> None:
        self.rules.pop(rule_name, None)

    def clear_rules(self) -> None:
        self.rules.clear()

    def get_rule(self, rule_name: str) -> Optional[BaseRule]:
        return self.rules.get(rule_name)

    def reset(self) -> None:
        for rule in self.rules.values():
            rule.reset()

    def evaluate(self, tracks: List[TrackedObject], context: FrameContext) -> List[RuleViolation]:
        """
        Запуск всех активных правил на текущем кадре.
        :param tracks: список активных треков
        :param context: метаданные кадра
        :return: агрегированный список всех выявленных нарушений
        """
        all_violations: List[RuleViolation] = []
        tracks = [track for track in tracks if track.time_since_update == 0
                  and track.state not in (TrackState.LOST, TrackState.REMOVED)]

        for rule in list(self.rules.values()):
            if not rule.is_enabled:
                continue
            try:
                violations = rule.evaluate(tracks, context)
                if violations:
                    all_violations.extend(violations)
            except Exception as e:
                print(f"[RulesEngine] Ошибка выполнения правила '{rule.name}': {e}")

        return all_violations
