"""Tax Policy — immutable versioned tax policy with rules.

Contains TaxPolicy evaluator and rule matching engine.

Tax = f(Ledger, TaxPolicyVersion)
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from backend.accounting.db.pool import get_pool
from backend.accounting.models.enums import (
    TaxReasonCode,
    TaxRegisterType,
    TaxTreatment,
)


@dataclass
class TaxRule:
    """A single tax rule within a policy version."""
    id: str
    policy_version_id: str
    priority: int
    rule_code: str
    account_pattern: str | None
    direction: str | None
    register_type: str
    tax_treatment: str
    excluded: bool
    reason_code: str | None
    amount_multiplier: float


@dataclass
class TaxPolicyVersionInfo:
    """Snapshot of a tax policy version with its rules."""
    policy_version_id: str
    policy_id: str
    version: str
    tax_regime: str
    effective_from: date
    effective_to: date | None
    rules: list[TaxRule]
    rules_hash: str


@dataclass
class TaxRuleMatch:
    """Result of matching a tax rule against a ledger line."""
    matched: bool
    rule: TaxRule | None = None
    reason_code: str | None = None
    reason_text: str | None = None


class TaxPolicy:
    """Evaluates ledger lines against tax policy versions.

    TaxPolicy.evaluate(ledger_line) → TaxRuleMatch

    Immutable: changing a policy creates a new version.
    """

    def __init__(self):
        self._cache: dict[str, TaxPolicyVersionInfo] = {}

    async def get_active_policy_version(
        self,
        company_id: str,
        target_date: date | None = None,
    ) -> TaxPolicyVersionInfo | None:
        """Get the active tax policy version for a company on a given date."""
        pool = await get_pool()
        if target_date is None:
            target_date = date.today()

        async with pool.acquire() as conn:
            # Find company's tax regime first
            regime_row = await conn.fetchrow(
                """SELECT regime_type::text FROM accounting.tax_regime
                   WHERE company_id = $1 AND is_active = true LIMIT 1""",
                company_id,
            )
            if not regime_row:
                return None
            tax_regime = regime_row["regime_type"]
            if tax_regime == "usn_income":
                tax_regime = "USN_D"
            elif tax_regime == "usn_income_expense":
                tax_regime = "USN_DR"
            elif tax_regime == "osno":
                tax_regime = "GENERAL"

            # Find matching policy
            policy = await conn.fetchrow(
                """SELECT pv.id AS pv_id, pv.policy_id, pv.version,
                          pv.effective_from, pv.effective_to, pv.rules_hash,
                          p.tax_regime
                   FROM accounting.tax_policy_version pv
                   JOIN accounting.tax_policy p ON p.id = pv.policy_id
                   WHERE p.tax_regime = $1
                     AND pv.is_active = true
                     AND pv.effective_from <= $2
                     AND (pv.effective_to IS NULL OR pv.effective_to >= $2)
                   ORDER BY pv.effective_from DESC
                   LIMIT 1""",
                tax_regime,
                target_date,
            )
            if not policy:
                return None

            # Load rules
            rule_rows = await conn.fetch(
                """SELECT id, policy_version_id, priority, rule_code,
                          account_pattern, direction, register_type,
                          tax_treatment, excluded, reason_code,
                          amount_multiplier::text
                   FROM accounting.tax_rule
                   WHERE policy_version_id = $1
                   ORDER BY priority DESC""",
                policy["pv_id"],
            )

            rules = [
                TaxRule(
                    id=str(r["id"]),
                    policy_version_id=str(r["policy_version_id"]),
                    priority=r["priority"],
                    rule_code=r["rule_code"],
                    account_pattern=r["account_pattern"],
                    direction=r["direction"],
                    register_type=r["register_type"],
                    tax_treatment=r["tax_treatment"],
                    excluded=r["excluded"],
                    reason_code=r["reason_code"],
                    amount_multiplier=float(r["amount_multiplier"]),
                )
                for r in rule_rows
            ]

            info = TaxPolicyVersionInfo(
                policy_version_id=str(policy["pv_id"]),
                policy_id=str(policy["policy_id"]),
                version=policy["version"],
                tax_regime=policy["tax_regime"],
                effective_from=policy["effective_from"],
                effective_to=policy["effective_to"],
                rules=rules,
                rules_hash=policy["rules_hash"],
            )

            # Cache
            self._cache[company_id] = info
            return info

    def evaluate(
        self,
        account_code: str,
        direction: str,
        policy: TaxPolicyVersionInfo | None,
    ) -> TaxRuleMatch:
        """Evaluate a ledger line against a tax policy version.

        Priority chain: first matching rule wins (highest priority first).

        Args:
            account_code: Ledger account code (e.g. '90.01')
            direction: 'debit' or 'credit'
            policy: Active policy version (None = no policy active)

        Returns:
            TaxRuleMatch with matched rule or default exclusion.
        """
        if policy is None:
            return TaxRuleMatch(
                matched=True,
                reason_code=TaxReasonCode.NO_ACTIVE_POLICY.value,
                reason_text="No active tax policy found for company",
            )

        # Priority chain: highest priority first
        sorted_rules = sorted(policy.rules, key=lambda r: -r.priority)

        for rule in sorted_rules:
            # Check account pattern
            if rule.account_pattern and not self._match_account(
                account_code, rule.account_pattern
            ):
                continue

            # Check direction
            if rule.direction and rule.direction != direction:
                continue

            # Match found
            return TaxRuleMatch(
                matched=True,
                rule=rule,
                reason_code=rule.reason_code,
                reason_text=f"Rule {rule.rule_code}: {rule.register_type} / {rule.tax_treatment}",
            )

        # Default: excluded — no matching rule
        return TaxRuleMatch(
            matched=True,
            reason_code=TaxReasonCode.UNMAPPED_ACCOUNT.value,
            reason_text=f"No matching rule for account {account_code} / {direction}",
        )

    def _match_account(self, account_code: str, pattern: str) -> bool:
        """Match account code against a pattern (prefix match)."""
        if pattern.endswith("*"):
            return account_code.startswith(pattern[:-1])
        return account_code == pattern

    @staticmethod
    async def create_policy_version(
        name: str,
        tax_regime: str,
        version: str,
        effective_from: date,
        effective_to: date | None = None,
        rules: list[dict[str, Any]] | None = None,
    ) -> str:
        """Create a new tax policy with version and rules (idempotent)."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Upsert policy
            policy_row = await conn.fetchrow(
                """SELECT id FROM accounting.tax_policy WHERE name = $1""",
                name,
            )
            if not policy_row:
                policy_id = str(uuid.uuid4())
                await conn.execute(
                    """INSERT INTO accounting.tax_policy (id, name, description, tax_regime, is_active)
                       VALUES ($1, $2, $3, $4, true)""",
                    policy_id,
                    name,
                    f"Tax policy for {tax_regime}",
                    tax_regime,
                )
            else:
                policy_id = str(policy_row["id"])

            # Compute rules hash
            rules_hash_input = json.dumps(
                rules or [], sort_keys=True, ensure_ascii=False
            ).encode()
            rules_hash = hashlib.sha256(rules_hash_input).hexdigest()

            # Check if version already exists
            existing = await conn.fetchrow(
                """SELECT id FROM accounting.tax_policy_version
                   WHERE policy_id = $1 AND version = $2""",
                policy_id,
                version,
            )
            if existing:
                return str(existing["id"])

            # Create version
            pv_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO accounting.tax_policy_version
                   (id, policy_id, version, effective_from, effective_to, rules_hash, is_active)
                   VALUES ($1, $2, $3, $4, $5, $6, true)""",
                pv_id,
                policy_id,
                version,
                effective_from,
                effective_to,
                rules_hash,
            )

            # Create rules
            if rules:
                for i, r in enumerate(rules):
                    await conn.execute(
                        """INSERT INTO accounting.tax_rule
                           (id, policy_version_id, priority, rule_code,
                            account_pattern, direction, register_type,
                            tax_treatment, excluded, reason_code,
                            amount_multiplier)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
                        str(uuid.uuid4()),
                        pv_id,
                        len(rules) - i,
                        r.get("rule_code", f"rule_{i}"),
                        r.get("account_pattern"),
                        r.get("direction"),
                        r["register_type"],
                        r["tax_treatment"],
                        r.get("excluded", False),
                        r.get("reason_code"),
                        r.get("amount_multiplier", 1.0),
                    )

            return pv_id

    @staticmethod
    async def seed_default_policies() -> dict[str, str]:
        """Seed default tax policies for all regimes. Idempotent."""
        result = {}

        # USN_D (УСН Доходы)
        result["USN_D"] = await TaxPolicy.create_policy_version(
            name="USN Income (Standard)",
            tax_regime="USN_D",
            version="2026.01.01",
            effective_from=date(2026, 1, 1),
            rules=[
                {
                    "rule_code": "revenue_to_kudir",
                    "account_pattern": "90.01",
                    "direction": "credit",
                    "register_type": "KUDIR_INCOME",
                    "tax_treatment": "taxable",
                },
                {
                    "rule_code": "cash_receipt_to_kudir",
                    "account_pattern": "51",
                    "direction": "debit",
                    "register_type": "KUDIR_INCOME",
                    "tax_treatment": "taxable",
                },
                {
                    "rule_code": "balance_accounts_excluded",
                    "account_pattern": "76",
                    "direction": None,
                    "register_type": "EXCLUDED",
                    "tax_treatment": "excluded",
                    "excluded": True,
                    "reason_code": "balance_account",
                },
                {
                    "rule_code": "default_exclusion",
                    "account_pattern": None,
                    "direction": None,
                    "register_type": "EXCLUDED",
                    "tax_treatment": "excluded",
                    "excluded": True,
                    "reason_code": "unmapped_account",
                },
            ],
        )

        # USN_DR (УСН Доходы минус Расходы)
        result["USN_DR"] = await TaxPolicy.create_policy_version(
            name="USN Income-Expense (Standard)",
            tax_regime="USN_DR",
            version="2026.01.01",
            effective_from=date(2026, 1, 1),
            rules=[
                {
                    "rule_code": "revenue_to_kudir_income",
                    "account_pattern": "90.01",
                    "direction": "credit",
                    "register_type": "KUDIR_INCOME",
                    "tax_treatment": "taxable",
                },
                {
                    "rule_code": "expense_sales_to_kudir",
                    "account_pattern": "44",
                    "direction": "debit",
                    "register_type": "KUDIR_EXPENSE",
                    "tax_treatment": "deductible",
                },
                {
                    "rule_code": "expense_general_to_kudir",
                    "account_pattern": "26",
                    "direction": "debit",
                    "register_type": "KUDIR_EXPENSE",
                    "tax_treatment": "deductible",
                },
                {
                    "rule_code": "supplier_expense",
                    "account_pattern": "60",
                    "direction": "credit",
                    "register_type": "KUDIR_EXPENSE",
                    "tax_treatment": "deductible",
                },
                {
                    "rule_code": "balance_accounts_excluded",
                    "account_pattern": "76",
                    "direction": None,
                    "register_type": "EXCLUDED",
                    "tax_treatment": "excluded",
                    "excluded": True,
                    "reason_code": "balance_account",
                },
                {
                    "rule_code": "vat_account_excluded",
                    "account_pattern": "68",
                    "direction": None,
                    "register_type": "EXCLUDED",
                    "tax_treatment": "excluded",
                    "excluded": True,
                    "reason_code": "balance_account",
                },
                {
                    "rule_code": "default_exclusion",
                    "account_pattern": None,
                    "direction": None,
                    "register_type": "EXCLUDED",
                    "tax_treatment": "excluded",
                    "excluded": True,
                    "reason_code": "unmapped_account",
                },
            ],
        )

        # GENERAL (ОСНО)
        result["GENERAL"] = await TaxPolicy.create_policy_version(
            name="General Tax System (Standard)",
            tax_regime="GENERAL",
            version="2026.01.01",
            effective_from=date(2026, 1, 1),
            rules=[
                {
                    "rule_code": "revenue_to_general_income",
                    "account_pattern": "90.01",
                    "direction": "credit",
                    "register_type": "GENERAL_INCOME",
                    "tax_treatment": "taxable",
                },
                {
                    "rule_code": "vat_sales",
                    "account_pattern": "68",
                    "direction": "credit",
                    "register_type": "VAT_SALES",
                    "tax_treatment": "taxable",
                },
                {
                    "rule_code": "vat_purchase",
                    "account_pattern": "19",
                    "direction": "debit",
                    "register_type": "VAT_PURCHASE",
                    "tax_treatment": "deductible",
                },
                {
                    "rule_code": "expense_general",
                    "account_pattern": "44",
                    "direction": "debit",
                    "register_type": "GENERAL_EXPENSE",
                    "tax_treatment": "deductible",
                },
                {
                    "rule_code": "expense_admin",
                    "account_pattern": "26",
                    "direction": "debit",
                    "register_type": "GENERAL_EXPENSE",
                    "tax_treatment": "deductible",
                },
                {
                    "rule_code": "balance_accounts_excluded",
                    "account_pattern": "76",
                    "direction": None,
                    "register_type": "EXCLUDED",
                    "tax_treatment": "excluded",
                    "excluded": True,
                    "reason_code": "balance_account",
                },
                {
                    "rule_code": "default_exclusion",
                    "account_pattern": None,
                    "direction": None,
                    "register_type": "EXCLUDED",
                    "tax_treatment": "excluded",
                    "excluded": True,
                    "reason_code": "unmapped_account",
                },
            ],
        )

        return result
