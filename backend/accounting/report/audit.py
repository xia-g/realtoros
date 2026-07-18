"""AI Audit Engine — read-only validation layer.

AuditEngine.audit(report_snapshot) → AuditResult

Invariant: AI is read-only. Cannot affect report content or status beyond 'ai_reviewed'.
Categories: formal, logical, contextual, cross_check.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.accounting.db.pool import get_pool


@dataclass(frozen=True)
class AuditFinding:
    finding_id: str
    severity: str          # critical | warning | info
    category: str          # formal | logical | contextual | cross_check
    field_path: str | None
    description: str
    evidence: str | None
    suggested_action: str  # verify | recalculate | exclude | none


@dataclass
class AuditResult:
    result_id: str
    report_id: str
    audit_model_version: str
    risk_score: float
    approved: bool
    findings: list[AuditFinding] = field(default_factory=list)
    supersedes: str | None = None


class AuditEngine:
    """Read-only audit engine.

    Passes:
      1. Formal — arithmetic, control ratios, required fields
      2. Logical — anomalies, outliers, sudden changes
      3. Contextual — regime vs report type, missing registers
      4. Cross-Check — ledger totals vs register totals
    """

    AUDIT_MODEL_VERSION = "2026.06.01"

    @staticmethod
    async def audit(report_id: str) -> AuditResult:
        """Run all audit passes on a report snapshot."""
        pool = await get_pool()
        findings: list[AuditFinding] = []

        async with pool.acquire() as conn:
            # Load report
            report = await conn.fetchrow(
                "SELECT * FROM accounting.report_draft WHERE id = $1",
                report_id,
            )
            if not report:
                raise ValueError(f"Report {report_id} not found")

            cells = await conn.fetch(
                "SELECT * FROM accounting.report_cell WHERE report_id = $1 ORDER BY cell_code",
                report_id,
            )

            company_id = report["company_id"]
            template_version_id = report["template_version_id"]

            # Load template fields + control ratios
            tv = await conn.fetchrow(
                "SELECT * FROM accounting.report_template_version WHERE id = $1",
                template_version_id,
            )
            control_ratios = json.loads(tv["control_ratios"]) if tv and isinstance(tv["control_ratios"], str) else (tv["control_ratios"] if tv else [])
            fields = json.loads(tv["fields_json"]) if tv and isinstance(tv["fields_json"], str) else (tv["fields_json"] if tv else {})
            formulas = json.loads(tv["formulas_json"]) if tv and isinstance(tv["formulas_json"], str) else (tv["formulas_json"] if tv else {})

            async with pool.acquire() as conn2:
                registers = await conn2.fetch(
                    "SELECT * FROM accounting.tax_register WHERE company_id = $1 AND is_current = true",
                    company_id,
                )

            cell_dict = {c["cell_code"]: c for c in cells}
            reg_dict = {r["register_type"]: dict(r) for r in registers}

            # ── 4.1 Formal Pass ─────────────────────────────────────
            findings.extend(AuditEngine._formal_pass(cells, cell_dict, fields, control_ratios, formulas))

            # ── 4.2 Logical Pass ────────────────────────────────────
            findings.extend(AuditEngine._logical_pass(cell_dict))

            # ── 4.3 Contextual Pass ─────────────────────────────────
            findings.extend(await AuditEngine._contextual_pass(company_id, reg_dict, fields, pool))

            # ── 4.4 Cross-Check Pass ────────────────────────────────
            findings.extend(await AuditEngine._cross_check_pass(company_id, report, reg_dict, pool))

        # Compute risk score
        risk_score = AuditEngine._compute_risk_score(findings)
        approved = risk_score < 0.2

        result_id = str(uuid.uuid4())
        return AuditResult(
            result_id=result_id,
            report_id=report_id,
            audit_model_version=AuditEngine.AUDIT_MODEL_VERSION,
            risk_score=round(risk_score, 4),
            approved=approved,
            findings=findings,
        )

    @staticmethod
    def _formal_pass(cells, cell_dict, fields, control_ratios, formulas) -> list[AuditFinding]:
        findings = []

        # Check all required fields have values
        for field_key, field_info in fields.items():
            if field_info.get("type") == "section":
                continue
            cell = cell_dict.get(field_key)
            if not cell or (cell["value"] is None and cell["value_numeric"] is None):
                findings.append(AuditFinding(
                    finding_id=str(uuid.uuid4()),
                    severity="critical",
                    category="formal",
                    field_path=field_key,
                    description=f"Required field {field_key} ({field_info.get('label', '')}) is empty",
                    evidence=None,
                    suggested_action="verify",
                ))

        # Check arithmetic (summations)
        for formula_key, formula in formulas.items():
            if " - " in formula:
                # Check result is >= 0 for subtraction formulas
                cell = cell_dict.get(formula_key)
                if cell and cell["value_numeric"] is not None and cell["value_numeric"] < -0.01:
                    findings.append(AuditFinding(
                        finding_id=str(uuid.uuid4()),
                        severity="critical",
                        category="formal",
                        field_path=formula_key,
                        description=f"Negative value in field {formula_key}: {cell['value_numeric']:.2f}",
                        evidence=f"Formula: {formula}",
                        suggested_action="verify",
                    ))

        # Check control ratios
        for ratio in (control_ratios or []):
            try:
                # Basic ratio parsing: "field >= 0"
                parts = ratio.replace(" ", "").split(">=")
                if len(parts) == 2:
                    field_name = parts[0]
                    cell = cell_dict.get(field_name)
                    if cell and cell["value_numeric"] is not None and cell["value_numeric"] < 0:
                        findings.append(AuditFinding(
                            finding_id=str(uuid.uuid4()),
                            severity="critical",
                            category="formal",
                            field_path=field_name,
                            description=f"Control ratio violated: {ratio} (current: {cell['value_numeric']:.2f})",
                            evidence=f"Control ratio: {ratio}",
                            suggested_action="verify",
                        ))
            except Exception:
                pass

        return findings

    @staticmethod
    def _logical_pass(cell_dict) -> list[AuditFinding]:
        findings = []

        # Check for extreme values
        numeric_values = [
            c["value_numeric"] for c in cell_dict.values()
            if c["value_numeric"] is not None
        ]

        if len(numeric_values) >= 3:
            mean = statistics.mean(numeric_values)
            stdev = statistics.stdev(numeric_values) if len(numeric_values) > 1 else 0

            for cell_code, cell in cell_dict.items():
                if cell["value_numeric"] is not None and stdev > 0:
                    z_score = abs(cell["value_numeric"] - mean) / stdev
                    if z_score > 3:
                        findings.append(AuditFinding(
                            finding_id=str(uuid.uuid4()),
                            severity="warning",
                            category="logical",
                            field_path=cell_code,
                            description=f"Anomalous value: {cell['value_numeric']:.2f} "
                                        f"(z-score={z_score:.1f}, mean={mean:.2f})",
                            evidence=f"Statistical outlier detection",
                            suggested_action="verify",
                        ))

        # Check for negative values in amount fields
        for cell_code, cell in cell_dict.items():
            if cell["value_numeric"] is not None and cell["value_numeric"] < 0:
                if "налог" in cell_code.lower() or "line_030" in cell_code or "line_040" in cell_code:
                    findings.append(AuditFinding(
                        finding_id=str(uuid.uuid4()),
                        severity="warning",
                        category="logical",
                        field_path=cell_code,
                        description=f"Negative value in tax field: {cell['value_numeric']:.2f}",
                        evidence="Tax amounts should typically be non-negative",
                        suggested_action="verify",
                    ))

        return findings

    @staticmethod
    async def _contextual_pass(company_id, reg_dict, fields, pool) -> list[AuditFinding]:
        findings = []

        async with pool.acquire() as conn:
            regime = await conn.fetchrow(
                "SELECT regime_type FROM accounting.tax_regime WHERE company_id = $1 AND is_active = true",
                company_id,
            )

        if not regime:
            findings.append(AuditFinding(
                finding_id=str(uuid.uuid4()),
                severity="critical",
                category="contextual",
                field_path=None,
                description="No active tax regime found for company",
                evidence=None,
                suggested_action="verify",
            ))
            return findings

        regime_type = regime["regime_type"]

        # Check: USN company shouldn't have VAT registers
        if regime_type in ("usn_income", "usn_income_expense"):
            if "VAT_SALES" in reg_dict or "VAT_PURCHASE" in reg_dict:
                findings.append(AuditFinding(
                    finding_id=str(uuid.uuid4()),
                    severity="warning",
                    category="contextual",
                    field_path=None,
                    description=f"VAT registers present for USN regime ({regime_type})",
                    evidence=f"Found VAT registers: VAT_SALES, VAT_PURCHASE",
                    suggested_action="verify",
                ))

        # Check: GENERAL company should have VAT and General registers
        if regime_type == "osno":
            missing = []
            for rt in ["VAT_SALES", "GENERAL_INCOME", "GENERAL_EXPENSE"]:
                if rt not in reg_dict:
                    missing.append(rt)
            if missing:
                findings.append(AuditFinding(
                    finding_id=str(uuid.uuid4()),
                    severity="warning",
                    category="contextual",
                    field_path=None,
                    description=f"Missing expected registers for GENERAL regime: {', '.join(missing)}",
                    evidence=f"Regime: {regime_type}, found: {list(reg_dict.keys())}",
                    suggested_action="verify",
                ))

        return findings

    @staticmethod
    async def _cross_check_pass(company_id, report, reg_dict, pool) -> list[AuditFinding]:
        findings = []

        async with pool.acquire() as conn:
            ledger_income = await conn.fetchval(
                """SELECT COALESCE(SUM(ll.amount), 0)
                   FROM accounting.ledger_line ll
                   JOIN accounting.ledger_entry le ON le.id = ll.entry_id
                   WHERE le.company_id = $1 AND ll.direction = 'credit'
                     AND ll.account_code LIKE '90.%'""",
                company_id,
            )

        # Cross-check: Ledger credit-side revenue vs KUDIR_INCOME register
        kudir_income = reg_dict.get("KUDIR_INCOME", {}).get("total_amount", 0)
        if kudir_income and float(kudir_income) > 0:
            diff_pct = abs(float(ledger_income) - float(kudir_income)) / float(kudir_income) * 100
            if diff_pct > 5:
                findings.append(AuditFinding(
                    finding_id=str(uuid.uuid4()),
                    severity="warning",
                    category="cross_check",
                    field_path=None,
                    description=f"Ledger revenue ({float(ledger_income):.0f}) differs "
                                f"from KUDIR_INCOME ({float(kudir_income):.0f}) by {diff_pct:.1f}%",
                    evidence=f"Ledger CR 90.* = {float(ledger_income):.0f}, "
                             f"Register KUDIR_INCOME = {float(kudir_income):.0f}",
                    suggested_action="verify",
                ))

        return findings

    @staticmethod
    def _compute_risk_score(findings: list[AuditFinding]) -> float:
        severity_weights = {
            "critical": 1.0,
            "warning": 0.5,
            "info": 0.1,
        }
        if not findings:
            return 0.0

        total_weight = sum(severity_weights.get(f.severity, 0.1) for f in findings)
        max_weight = len(findings) * 1.0  # max if all critical
        return total_weight / max_weight if max_weight > 0 else 0.0

    @staticmethod
    async def save(result: AuditResult) -> str:
        """Persist audit result with findings."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Supersede previous audit result
            old = await conn.fetchval(
                "SELECT id FROM accounting.report_audit_result "
                "WHERE report_id = $1 ORDER BY created_at DESC LIMIT 1",
                result.report_id,
            )
            if old:
                result.supersedes = str(old)

            # Insert result
            await conn.execute(
                """INSERT INTO accounting.report_audit_result
                   (id, report_id, audit_model_version, risk_score, approved, supersedes)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                result.result_id,
                result.report_id,
                result.audit_model_version,
                result.risk_score,
                result.approved,
                result.supersedes,
            )

            # Insert findings
            for f in result.findings:
                await conn.execute(
                    """INSERT INTO accounting.report_audit_finding
                       (id, audit_result_id, severity, category, field_path, description, evidence, suggested_action)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                    f.finding_id, result.result_id, f.severity, f.category,
                    f.field_path, f.description, f.evidence, f.suggested_action,
                )

            # Update report status to ai_reviewed
            await conn.execute(
                "UPDATE accounting.report_draft SET status = 'ai_reviewed', updated_at = now() WHERE id = $1",
                result.report_id,
            )

            return result.result_id
