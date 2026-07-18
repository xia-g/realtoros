"""Posting rule: Expense Payment — DR 44 (or 26), CR 60."""

from backend.accounting.ledger.posting.base import PostingRule, PostingResult, PostingLine


class ExpensePayment(PostingRule):
    rule_code = "expense_payment"
    priority = 80
    description = "Expense/purchase → cost recognition"

    def supports(self, event_type: str, decision: dict, explanations: list[dict]) -> bool:
        return event_type in ("purchase", "agent_commission")

    def generate(self, event_type: str, decision: dict, explanations: list[dict]) -> PostingResult:
        amount = float(decision["amount"])
        currency = decision.get("currency", "RUB")
        return PostingResult(rule_code=self.rule_code, lines=[
            PostingLine("44", "debit", amount, currency),
            PostingLine("60", "credit", amount, currency),
        ])
