"""Rule: High-value events require manual review."""

from backend.accounting.rules.base import Rule
from backend.accounting.rules.engine import RuleResult


class AmountThresholdRule(Rule):
    rule_code = "amount_threshold_requires_review"
    priority = 60
    description = "Events above amount threshold require manual review"

    THRESHOLD = 1_000_000.0  # 1M RUB
    REVIEW_THRESHOLD = 500_000.0  # 500k RUB

    def supports(self, event: dict, snapshot: dict) -> bool:
        amount = event.get("amount", 0)
        return amount >= self.REVIEW_THRESHOLD

    def evaluate(self, event: dict, snapshot: dict) -> RuleResult:
        amount = float(event.get("amount", 0))
        event_type = event.get("event_type", "")

        if amount >= self.THRESHOLD:
            # Mark as requires_review — the Decision aggregate will set decision_state=REVIEW_REQUIRED
            return RuleResult(
                rule_code=self.rule_code,
                included=False,
                weight=0.9,
                message=f"Amount {amount:,.2f} exceeds threshold {self.THRESHOLD:,.0f} — requires manual approval",
                payload={"amount": amount, "threshold": self.THRESHOLD, "event_type": event_type, "review": True},
            )

        return RuleResult(
            rule_code=self.rule_code,
            included=True,
            weight=0.4,
            message=f"Amount {amount:,.2f} below threshold — auto-approved",
            payload={"amount": amount, "threshold": self.THRESHOLD},
        )
