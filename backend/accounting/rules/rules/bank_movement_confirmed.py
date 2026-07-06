"""Rule: Bank movements should be confirmed by matching documents."""

from backend.accounting.rules.base import Rule
from backend.accounting.rules.engine import RuleResult


class BankMovementConfirmed(Rule):
    rule_code = "bank_movement_confirmed"
    priority = 80
    description = "Bank inflow/outflow events should have a confirming document"

    def supports(self, event: dict, snapshot: dict) -> bool:
        return event.get("event_type") in ("bank_inflow", "bank_outflow")

    def evaluate(self, event: dict, snapshot: dict) -> RuleResult:
        docs = snapshot.get("documents", [])
        txns = snapshot.get("transactions", [])

        has_confirmation = any(d.get("role") == "confirming" for d in docs)
        has_transaction = len(txns) > 0

        if has_confirmation and has_transaction:
            return RuleResult(
                rule_code=self.rule_code,
                included=True,
                weight=0.7,
                message="Bank movement confirmed by document and transaction",
                payload={"documents": len(docs), "transactions": len(txns)},
            )

        if has_transaction:
            return RuleResult(
                rule_code=self.rule_code,
                included=True,
                weight=0.5,
                message="Bank movement has transaction record but no confirming document",
                payload={"documents": len(docs), "transactions": len(txns)},
            )

        return RuleResult(
            rule_code=self.rule_code,
            included=False,
            weight=0.7,
            message="No transaction or confirming document for this bank movement",
            payload={"documents": len(docs), "transactions": len(txns)},
        )
