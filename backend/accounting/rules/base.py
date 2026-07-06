"""Base Rule interface — all rules must implement this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.accounting.rules.engine import RuleResult


class Rule(ABC):
    """A single business rule that can be applied to an accounting event."""

    rule_code: str = ""
    priority: int = 0
    description: str = ""

    @abstractmethod
    def supports(self, event: dict, snapshot: dict) -> bool:
        """Return True if this rule applies to the given event + snapshot."""
        ...

    @abstractmethod
    def evaluate(self, event: dict, snapshot: dict) -> RuleResult:
        """Evaluate the rule and return a result.

        Args:
            event: The accounting_event dict (from DB)
            snapshot: The recognition_snapshot inputs_json

        Returns:
            RuleResult with included=True/False, weight, message, payload
        """
        ...
