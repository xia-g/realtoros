"""Rule engine — evaluates events against rulesets.

Invariants:
- Decision = f(Event, Snapshot, RulesetVersion)
- Engine reads ONLY: accounting_event, recognition_snapshot, tax_regime
- NEVER reads live documents, bank_transactions, CRM, users
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuleResult:
    """Result of a single rule evaluation."""

    rule_code: str
    included: bool
    weight: float
    message: str
    payload: dict | None = None


@dataclass
class Decision:
    """Aggregated decision from all applicable rules."""

    included: bool
    reason: str
    explanations: list[RuleResult] = field(default_factory=list)
    requires_review: bool = False

    @classmethod
    def aggregate(cls, results: list[RuleResult]) -> Decision:
        """Aggregate multiple rule results into a single decision.

        All rules must include for the event to be included.
        Any positive-weight exclusion triggers exclusion.
        Review triggers are additive.
        """
        if not results:
            return cls(included=True, reason="No rules matched — default include")

        weight_sum = sum(r.weight for r in results)
        included = all(r.included for r in results)
        requires_review = any("review" in r.rule_code.lower() for r in results if not r.included)

        # Build explanation
        reasons = [r.message for r in results if not r.included]
        if included:
            reason = f"All {len(results)} rules passed"
        else:
            reason = "; ".join(reasons)

        return cls(
            included=included,
            reason=reason,
            explanations=results,
            requires_review=requires_review,
        )
