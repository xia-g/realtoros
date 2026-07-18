"""Rule registry — discovers and orders rules by priority."""

from __future__ import annotations

from typing import Any

from backend.accounting.rules.base import Rule
from backend.accounting.rules.engine import Decision, RuleResult


class RuleRegistry:
    """Registry of all business rules. Rules are sorted by priority (desc)."""

    def __init__(self):
        self._rules: list[Rule] = []

    def register(self, rule: Rule) -> None:
        self._rules.append(rule)
        self._rules.sort(key=lambda r: -r.priority)

    def get_applicable(self, event: dict, snapshot: dict) -> list[Rule]:
        return [r for r in self._rules if r.supports(event, snapshot)]

    def evaluate_all(self, event: dict, snapshot: dict) -> Decision:
        applicable = self.get_applicable(event, snapshot)
        results = [r.evaluate(event, snapshot) for r in applicable]
        return Decision.aggregate(results)

    @property
    def rules(self) -> list[Rule]:
        return list(self._rules)


# Global singleton
_registry: RuleRegistry | None = None


def get_registry() -> RuleRegistry:
    global _registry
    if _registry is None:
        _registry = RuleRegistry()
        # Auto-register built-in rules
        from backend.accounting.rules.rules.has_supporting_document import HasSupportingDocument
        from backend.accounting.rules.rules.expense_allowed_for_usn import ExpenseAllowedForUSN
        from backend.accounting.rules.rules.bank_movement_confirmed import BankMovementConfirmed
        from backend.accounting.rules.rules.amount_threshold import AmountThresholdRule

        _registry.register(HasSupportingDocument())
        _registry.register(ExpenseAllowedForUSN())
        _registry.register(BankMovementConfirmed())
        _registry.register(AmountThresholdRule())

    return _registry
