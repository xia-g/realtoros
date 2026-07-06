"""Report Generator — deterministic report generation engine.

ReportGenerator.generate(tax_register, template_version, period) → ReportDraft

Invariant: Report = f(TaxRegister, TemplateVersion)
Invariant: generate() × N = identical report_hash
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from backend.accounting.db.pool import get_pool
from backend.accounting.report.template import ReportTemplateVersion


@dataclass
class ReportCell:
    """A single cell in a generated report."""
    cell_code: str
    value: str | float | None
    value_numeric: float | None
    source_hash: str
    template_field_id: str | None
    formula_applied: str | None


@dataclass
class ReportDraft:
    """A complete generated report (materialized projection)."""
    report_id: str
    report_version: int
    company_id: str
    template_version_id: str
    register_version_id: str | None
    tax_policy_version: str | None
    tax_period_id: str | None
    status: str = "draft"
    report_hash: str = ""
    cells: list[ReportCell] = field(default_factory=list)
    total_income: float | None = None
    total_expense: float | None = None
    total_tax: float | None = None


class ReportGenerator:
    """Deterministic report generator.

    Pure function: generate(tax_register, template, period) → ReportDraft.

    No external data. No AI. No randomness.
    """

    @staticmethod
    async def generate(
        company_id: str,
        template_version: ReportTemplateVersion,
        tax_period_id: str | None = None,
    ) -> ReportDraft:
        """Generate a report draft from tax registers and template."""
        pool = await get_pool()

        # 1. Load tax register data
        register_totals = {}
        async with pool.acquire() as conn:
            registers = await conn.fetch(
                """SELECT register_type, total_amount::text, register_version, policy_version_id
                   FROM accounting.tax_register
                   WHERE company_id = $1 AND tax_period_id = $2 AND is_current = true""",
                company_id,
                tax_period_id,
            )
            for r in registers:
                register_totals[r["register_type"]] = {
                    "total": float(r["total_amount"]),
                    "version": r["register_version"],
                    "policy_version_id": str(r["policy_version_id"]) if r["policy_version_id"] else None,
                }

        # 2. Resolve register_version for deterministic linking
        register_version_id = None
        tax_policy_version = None
        for rt, data in register_totals.items():
            if data.get("policy_version_id"):
                tax_policy_version = data["policy_version_id"]

        # 3. Build cells from template fields
        cells: list[ReportCell] = []
        fields = template_version.fields or {}
        formulas = template_version.formulas or {}

        # Process template fields in order
        field_keys = sorted(fields.keys())

        for key in field_keys:
            field = fields[key]
            field_type = field.get("type", "string")
            source = field.get("source", "")

            # Resolve value from register_totals
            value: str | float | None = None
            value_numeric: float | None = None
            formula = formulas.get(key)

            if source and source in register_totals:
                value = register_totals[source]["total"]
                value_numeric = float(value) if value else None
                formula_applied = None
            elif source:
                # Source not available — zero
                value = 0
                value_numeric = 0.0
                formula_applied = None

            # If a formula exists, compute
            if formula and value_numeric is not None:
                formula_applied = formula
                value_numeric = ReportGenerator._evaluate_formula(
                    formula, {k: v["total"] for k, v in register_totals.items()
                              if isinstance(v["total"], (int, float))}
                )
                value = value_numeric

            # Build source_hash for determinism
            source_hash_input = {
                "cell_code": key,
                "template_version_id": template_version.id,
                "register_sources": {k: v["total"] for k, v in register_totals.items()},
                "formula": formula,
            }
            source_hash = hashlib.sha256(
                json.dumps(source_hash_input, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()

            cells.append(ReportCell(
                cell_code=key,
                value=str(value) if value is not None else None,
                value_numeric=value_numeric,
                source_hash=source_hash,
                template_field_id=key,
                formula_applied=formula_applied if formula else None,
            ))

        # 4. Compute report totals
        total_income = register_totals.get("KUDIR_INCOME", {}).get("total") or \
                       register_totals.get("GENERAL_INCOME", {}).get("total")
        total_expense = register_totals.get("KUDIR_EXPENSE", {}).get("total") or \
                        register_totals.get("GENERAL_EXPENSE", {}).get("total")

        # Find tax cell value
        total_tax = None
        for c in cells:
            if "_tax" in c.cell_code.lower() or "налог" in (fields.get(c.cell_code, {}).get("label", "")).lower():
                total_tax = c.value_numeric
                break

        # 5. Compute report_hash (deterministic)
        hash_input = {
            "template_version_id": template_version.id,
            "register_totals": {k: v["total"] for k, v in register_totals.items()},
            "cells": sorted([(c.cell_code, c.value_numeric, c.source_hash) for c in cells],
                           key=lambda x: x[0]),
        }
        report_hash = hashlib.sha256(
            json.dumps(hash_input, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()

        report_id = str(uuid.uuid4())

        return ReportDraft(
            report_id=report_id,
            report_version=1,
            company_id=company_id,
            template_version_id=template_version.id,
            register_version_id=register_version_id,
            tax_policy_version=tax_policy_version,
            tax_period_id=tax_period_id,
            status="draft",
            report_hash=report_hash,
            cells=cells,
            total_income=total_income,
            total_expense=total_expense,
            total_tax=total_tax,
        )

    @staticmethod
    def _evaluate_formula(formula: str, variables: dict[str, float]) -> float:
        """Evaluate a formula string with register variable substitution.

        Supported: +, -, *, /, (), direct values, variable references.
        """
        import re

        # Replace variable references (e.g. section_1.line_010) with values
        # Also handle numeric literals in formula (e.g. "0.06", "0.15", "0.20")
        # Formula pattern: "section_1.line_020 * 0.06"
        def resolve_var(match):
            name = match.group(0)
            if name in variables:
                return str(variables[name])
            # Try matching with section_X pattern
            # Variables are already in the dict by register type
            return name

        # First pass: replace known variables
        processed = formula
        for var_name, var_value in sorted(variables.items(), key=lambda x: -len(x[0])):
            processed = processed.replace(var_name, str(var_value))

        # Safe eval — only arithmetic operators, floats, parens
        if not re.match(r'^[\d\s\+\-\*\/\(\)\.]+$', processed):
            raise ValueError(f"Unsafe formula: {formula} (resolved: {processed})")

        try:
            result = eval(processed)
            return round(float(result), 2)
        except Exception as e:
            raise ValueError(f"Formula evaluation failed: {formula} → {processed}: {e}")

    @staticmethod
    async def save(draft: ReportDraft) -> str:
        """Persist a report draft with all cells."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Check for existing drafts — create new version
            last_version = await conn.fetchval(
                "SELECT COALESCE(MAX(report_version), 0) FROM accounting.report_draft "
                "WHERE company_id = $1 AND tax_period_id = $2 AND template_version_id = $3",
                draft.company_id,
                draft.tax_period_id,
                draft.template_version_id,
            )
            new_version = max(last_version + 1, draft.report_version) if last_version else draft.report_version

            # Check if identical hash already exists (idempotent)
            existing = await conn.fetchval(
                "SELECT id FROM accounting.report_draft WHERE report_hash = $1 LIMIT 1",
                draft.report_hash,
            )
            if existing:
                return str(existing)

            # Insert
            report_id = draft.report_id or str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO accounting.report_draft
                   (id, report_version, company_id, template_version_id,
                    register_version_id, tax_policy_version, tax_period_id,
                    status, report_hash, generated_at,
                    total_income, total_expense, total_tax)
                   VALUES ($1, $2, $3, $4, $5, $6, $7,
                           'draft', $8, now(),
                           $9, $10, $11)""",
                report_id, new_version, draft.company_id, draft.template_version_id,
                draft.register_version_id, draft.tax_policy_version, draft.tax_period_id,
                draft.report_hash,
                draft.total_income, draft.total_expense, draft.total_tax,
            )

            # Insert cells
            for cell in draft.cells:
                await conn.execute(
                    """INSERT INTO accounting.report_cell
                       (id, report_id, cell_code, value, value_numeric, source_hash,
                        template_field_id, formula_applied)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                    str(uuid.uuid4()), report_id, cell.cell_code,
                    cell.value, cell.value_numeric, cell.source_hash,
                    cell.template_field_id, cell.formula_applied,
                )

            return report_id
