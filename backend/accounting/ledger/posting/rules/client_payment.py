"""Posting rule: Client Payment — DR 51, CR 62."""

from backend.accounting.ledger.posting.base import PostingRule, PostingResult, PostingLine


class ClientPayment(PostingRule):
    rule_code = "client_payment"
    priority = 90
    description = "Client payment → cash receipt"

    def supports(self, event_type: str, decision: dict, explanations: list[dict]) -> bool:
        return event_type in ("client_payment", "bank_inflow")

    def generate(self, event_type: str, decision: dict, explanations: list[dict]) -> PostingResult:
        amount = float(decision["amount"])
        currency = decision.get("currency", "RUB")
        return PostingResult(rule_code=self.rule_code, lines=[
            PostingLine("51", "debit", amount, currency),
            PostingLine("62", "credit", amount, currency),
        ])
