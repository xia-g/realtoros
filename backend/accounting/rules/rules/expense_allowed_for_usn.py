"""Rule: Expenses are only allowed under USN_INCOME_EXPENSE regime."""

from backend.accounting.rules.base import Rule
from backend.accounting.rules.engine import RuleResult


class ExpenseAllowedForUSN(Rule):
    rule_code = "expense_allowed_for_usn"
    priority = 90
    description = "Expenses require USN_INCOME_EXPENSE regime or document-based deduction"

    def supports(self, event: dict, snapshot: dict) -> bool:
        event_type = event.get("event_type", "")
        return event_type in ("purchase", "agent_commission", "bank_outflow")

    def evaluate(self, event: dict, snapshot: dict) -> RuleResult:
        regime = snapshot.get("tax_regime")
        regime_type = regime.get("regime_type") if regime else None

        if regime_type == "usn_income_expense":
            return RuleResult(
                rule_code=self.rule_code,
                included=True,
                weight=0.8,
                message="USN_INCOME_EXPENSE allows documented expenses",
                payload={"regime_type": regime_type},
            )

        if regime_type == "osno":
            return RuleResult(
                rule_code=self.rule_code,
                included=True,
                weight=0.8,
                message="OSNO allows all expenses",
                payload={"regime_type": regime_type},
            )

        if regime_type == "usn_income":
            return RuleResult(
                rule_code=self.rule_code,
                included=False,
                weight=0.8,
                message="USN_INCOME does not allow expense deductions",
                payload={"regime_type": regime_type},
            )

        # No regime found - require review
        return RuleResult(
            rule_code=self.rule_code,
            included=False,
            weight=0.5,
            message="Tax regime not found for this period — manual review required",
            payload={"regime_type": None},
        )
