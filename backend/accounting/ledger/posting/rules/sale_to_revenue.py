"""Posting rule: Sale to Revenue — DR 62, CR 90.01 (revenue) + DR 90.03, CR 68 (VAT)."""

from backend.accounting.ledger.posting.base import PostingRule, PostingResult, PostingLine


class SaleToRevenue(PostingRule):
    rule_code = "sale_to_revenue"
    priority = 100
    description = "Sale → revenue recognition + VAT"

    def supports(self, event_type: str, decision: dict, explanations: list[dict]) -> bool:
        return event_type in ("sale",)

    def generate(self, event_type: str, decision: dict, explanations: list[dict]) -> PostingResult:
        amount = float(decision["amount"])
        currency = decision.get("currency", "RUB")
        lines = [
            PostingLine("62", "debit", amount, currency),
            PostingLine("90.01", "credit", amount, currency),
        ]
        # VAT: 20/120 of the amount
        vat = round(amount * 20 / 120, 2)
        lines.append(PostingLine("90.03", "debit", vat, currency))
        lines.append(PostingLine("68", "credit", vat, currency))
        return PostingResult(rule_code=self.rule_code, lines=lines)
