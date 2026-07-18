"""Posting rule: Bank Transfer — DR 60 / CR 51 (outflow) or DR 51 / CR 62 (inflow)."""

from backend.accounting.ledger.posting.base import PostingRule, PostingResult, PostingLine


class BankTransfer(PostingRule):
    rule_code = "bank_transfer"
    priority = 70
    description = "Bank transfer → cash movement"

    def supports(self, event_type: str, decision: dict, explanations: list[dict]) -> bool:
        return event_type in ("bank_outflow", "transfer")

    def generate(self, event_type: str, decision: dict, explanations: list[dict]) -> PostingResult:
        amount = float(decision["amount"])
        currency = decision.get("currency", "RUB")
        if event_type == "bank_outflow":
            return PostingResult(rule_code=self.rule_code, lines=[
                PostingLine("60", "debit", amount, currency),
                PostingLine("51", "credit", amount, currency),
            ])
        # transfer: suspense
        return PostingResult(rule_code=self.rule_code, lines=[
            PostingLine("76", "debit", amount, currency),
            PostingLine("76", "credit", amount, currency),
        ])
