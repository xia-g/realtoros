"""Tax Explainability — builds the explainability chain for tax entries.

register_entry → assignment → ledger_line → posting → decision → explanation

Each tax entry must answer:
- Why is it included/excluded?
- Which rule determined this?
- What is the full chain back to the original decision?
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from backend.accounting.db.pool import get_pool


@dataclass
class TaxExplanation:
    """Full explainability chain for a register entry."""
    explanation_id: str
    register_entry_id: str
    assignment_id: str
    ledger_line_id: str
    ledger_entry_id: str
    register_type: str
    tax_treatment: str
    excluded: bool
    reason_code: str | None
    why_included: str | None
    why_excluded: str | None
    rule_code: str | None
    chain: dict[str, Any] | None


class TaxExplainer:
    """Builds the explainability chain for tax register entries.

    Chain:
      tax_register_entry
        └── tax_assignment (register_type, tax_treatment, reason_code)
              └── ledger_line (account_code, amount, direction)
                    └── ledger_entry (entry_date, batch_id)
                          └── posting_decision_link (decision_id, posting_rule_code)
                                └── accounting_decision (included, reason)
                                      └── decision_explanation[] (rule_code, weight, message)
    """

    @staticmethod
    async def explain_register_entry(entry_id: str) -> TaxExplanation | None:
        """Build full explainability chain for a single register entry."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            # 1. Load register entry
            entry = await conn.fetchrow(
                """SELECT id, register_id, assignment_id, ledger_line_id,
                          account_code, amount, direction, tax_treatment, excluded
                   FROM accounting.tax_register_entry WHERE id = $1""",
                entry_id,
            )
            if not entry:
                return None

            # 2. Load assignment
            assig = await conn.fetchrow(
                """SELECT ta.*, tr.rule_code
                   FROM accounting.tax_assignment ta
                   LEFT JOIN accounting.tax_rule tr ON tr.id = ta.tax_rule_id
                   WHERE ta.id = $1""",
                entry["assignment_id"],
            )
            if not assig:
                return None

            # 3. Load ledger line → entry → posting link → decision
            line = await conn.fetchrow(
                "SELECT id, entry_id, account_code, direction, amount FROM accounting.ledger_line WHERE id = $1",
                entry["ledger_line_id"],
            )
            ledger_entry_id = line["entry_id"] if line else None

            ledger_entry = None
            pdl = None
            decision = None
            explanations = None
            if ledger_entry_id:
                ledger_entry = await conn.fetchrow(
                    "SELECT id, batch_id, entry_date, description FROM accounting.ledger_entry WHERE id = $1",
                    ledger_entry_id,
                )
                if ledger_entry:
                    pdl = await conn.fetchrow(
                        """SELECT id, decision_id, posting_rule_code, posting_rule_version
                           FROM accounting.posting_decision_link
                           WHERE batch_id = $1 LIMIT 1""",
                        ledger_entry["batch_id"],
                    )
                    if pdl:
                        decision = await conn.fetchrow(
                            """SELECT id, event_id, included, reason, decision_version,
                                      ruleset_version
                               FROM accounting.accounting_decision WHERE id = $1""",
                            pdl["decision_id"],
                        )
                        if decision:
                            expls = await conn.fetch(
                                "SELECT rule_code, weight, message FROM accounting.decision_explanation WHERE decision_id = $1",
                                decision["id"],
                            )
                            explanations = [dict(e) for e in expls] if expls else None

            # 4. Build chain
            chain = {
                "register_entry": {
                    "id": str(entry["id"]),
                    "account_code": entry["account_code"],
                    "amount": float(entry["amount"]),
                    "direction": entry["direction"],
                },
                "tax_assignment": {
                    "id": str(assig["id"]),
                    "register_type": assig["register_type"],
                    "tax_treatment": assig["tax_treatment"],
                    "excluded": assig["excluded"],
                    "reason_code": assig["reason_code"],
                    "rule_code": assig.get("rule_code"),
                },
                "ledger_line": dict(line) if line else None,
                "ledger_entry": dict(ledger_entry) if ledger_entry else None,
                "posting_link": dict(pdl) if pdl else None,
                "decision": dict(decision) if decision else None,
                "decision_explanations": explanations,
            }

            # 5. Build why_included / why_excluded
            why_included = None
            why_excluded = None
            if assig["excluded"]:
                why_excluded = TaxExplainer._reason_text(
                    assig["reason_code"],
                    entry["account_code"],
                    assig.get("rule_code"),
                )
                why_included = None
            else:
                why_included = TaxExplainer._reason_text(
                    assig["reason_code"],
                    entry["account_code"],
                    assig.get("rule_code"),
                )
                why_excluded = None

            return TaxExplanation(
                explanation_id=str(uuid.uuid4()),
                register_entry_id=str(entry["id"]),
                assignment_id=str(assig["id"]),
                ledger_line_id=str(entry["ledger_line_id"]),
                ledger_entry_id=str(ledger_entry_id) if ledger_entry_id else "",
                register_type=assig["register_type"],
                tax_treatment=assig["tax_treatment"],
                excluded=assig["excluded"],
                reason_code=assig["reason_code"],
                why_included=why_included,
                why_excluded=why_excluded,
                rule_code=assig.get("rule_code"),
                chain=chain,
            )

    @staticmethod
    def _reason_text(reason_code: str | None, account_code: str, rule_code: str | None) -> str:
        """Generate human-readable reason text."""
        reasons = {
            "balance_account": f"Account {account_code} is a balance account — excluded from tax registers",
            "unmapped_account": f"No tax rule found for account {account_code} — excluded by default",
            "internal_transfer": f"Internal transfer between accounts — not a taxable event",
            "vat_reclaim": f"VAT reclaim on account {account_code} — tracked in VAT register",
            "non_taxable_income": f"Income on account {account_code} is non-taxable under current regime",
            "non_deductible_expense": f"Expense on account {account_code} is non-deductible",
            "manual_exclusion": f"Manually excluded by accountant",
            "no_active_policy": f"No active tax policy — excluded by default",
        }
        if reason_code and reason_code in reasons:
            return reasons[reason_code]
        if rule_code:
            return f"Matched rule {rule_code}: account {account_code} → taxable register entry"
        return f"Account {account_code}: {reason_code or 'no reason'}"

    @staticmethod
    async def explain_register(register_id: str) -> list[TaxExplanation]:
        """Explain all entries in a register."""
        pool = await get_pool()
        explanations: list[TaxExplanation] = []

        async with pool.acquire() as conn:
            entries = await conn.fetch(
                "SELECT id FROM accounting.tax_register_entry WHERE register_id = $1",
                register_id,
            )

        for row in entries:
            expl = await TaxExplainer.explain_register_entry(str(row["id"]))
            if expl:
                explanations.append(expl)

        return explanations

    @staticmethod
    async def explain_by_ledger_line(ledger_line_id: str) -> TaxExplanation | None:
        """Explain tax treatment for a specific ledger line."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            assig = await conn.fetchrow(
                """SELECT id FROM accounting.tax_assignment
                   WHERE ledger_line_id = $1 AND is_current = true
                   LIMIT 1""",
                ledger_line_id,
            )
            if not assig:
                return None

            entry = await conn.fetchrow(
                "SELECT id FROM accounting.tax_register_entry WHERE assignment_id = $1 LIMIT 1",
                assig["id"],
            )
            if not entry:
                return None

        return await TaxExplainer.explain_register_entry(str(entry["id"]))
