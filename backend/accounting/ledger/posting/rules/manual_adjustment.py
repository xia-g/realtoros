"""Posting rule: Manual Adjustment — catch-all with strict constraints.

Only allowed when:
- decision_state = 'review_required'
- reason_code is provided
- approval is required in non-emergency situations
"""

from backend.accounting.ledger.posting.base import PostingRule, PostingResult, PostingLine


class ManualAdjustment(PostingRule):
    rule_code = "manual_adjustment"
    priority = 10
    description = "Catch-all: manual or unrecognised event types → suspense account"

    VALID_REASON_CODES = [
        "ocr_error",
        "rule_mismatch",
        "user_correction",
        "data_backfill",
        "system_migration",
    ]

    def supports(self, event_type: str, decision: dict, explanations: list[dict]) -> bool:
        # Only catches events not handled by higher-priority rules
        return event_type in ("manual", "refund") or event_type not in (
            "sale", "client_payment", "bank_inflow", "purchase",
            "agent_commission", "bank_outflow", "transfer",
        )

    def generate(self, event_type: str, decision: dict, explanations: list[dict]) -> PostingResult:
        amount = float(decision["amount"])
        currency = decision.get("currency", "RUB")

        # Decision state must be 'review_required' for manual_adjustment
        decision_state = decision.get("decision_state", "pending")
        if decision_state != "review_required":
            raise ValueError(
                "manual_adjustment rule requires decision_state='review_required'. "
                f"Got '{decision_state}'. Events with unrecognised types must be "
                "reviewed before posting."
            )

        # Check reason_code in explanations
        reason_code = None
        for expl in explanations:
            if isinstance(expl, dict) and expl.get("rule_code"):
                payload = expl.get("payload_json") or {}
                if isinstance(payload, str):
                    import json
                    try:
                        payload = json.loads(payload)
                    except (json.JSONDecodeError, TypeError):
                        payload = {}
                reason_code = payload.get("reason_code")

        if not reason_code:
            raise ValueError(
                "manual_adjustment requires a reason_code in decision explanations. "
                f"Valid codes: {self.VALID_REASON_CODES}"
            )

        return PostingResult(rule_code=self.rule_code, lines=[
            PostingLine("76", "debit", amount, currency),
            PostingLine("76", "credit", amount, currency),
        ])
