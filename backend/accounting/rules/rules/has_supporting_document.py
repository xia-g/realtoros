"""Rule: For SALE/PURCHASE events, a supporting document must be linked."""

from backend.accounting.rules.base import Rule
from backend.accounting.rules.engine import RuleResult


class HasSupportingDocument(Rule):
    rule_code = "has_supporting_document"
    priority = 100
    description = "For SALE/PURCHASE events, a supporting document must be linked"

    def supports(self, event: dict, snapshot: dict) -> bool:
        return event.get("event_type") in ("sale", "purchase")

    def evaluate(self, event: dict, snapshot: dict) -> RuleResult:
        docs = snapshot.get("documents", [])
        has_primary = any(d.get("role") == "primary" for d in docs)
        has_confirming = any(d.get("role") == "confirming" for d in docs)

        if has_primary or has_confirming:
            return RuleResult(
                rule_code=self.rule_code,
                included=True,
                weight=1.0,
                message=f"Document found: {len(docs)} linked document(s)",
                payload={"document_count": len(docs), "roles": [d["role"] for d in docs]},
            )

        return RuleResult(
            rule_code=self.rule_code,
            included=False,
            weight=1.0,
            message="No supporting document linked to this event",
            payload={"document_count": 0, "missing": ["primary", "confirming"]},
        )
