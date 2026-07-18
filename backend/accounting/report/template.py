"""Report Template System — versioned immutable templates.

TemplateProvider.get(report_code, tax_regime, period) → ReportTemplateVersion

Lifecycle: DISCOVERED → FETCHED → VALIDATED → ACTIVE → DEPRECATED → ARCHIVED
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from backend.accounting.db.pool import get_pool
from backend.accounting.models.enums import TemplateStatus


@dataclass(frozen=True)
class ReportTemplateVersion:
    """Immutable template version — mirrors DB row."""
    id: str
    template_id: str
    code: str
    name: str
    version: str
    status: str
    tax_regime: str
    effective_from: date
    effective_to: date | None
    checksum: str
    schema_version: str
    origin: str
    locale: str
    fields: dict
    formulas: dict
    control_ratios: list


class TemplateProvider:
    """Manages report template lifecycle and retrieval.

    Thread-safe, idempotent.
    """

    @staticmethod
    async def get_active(
        template_code: str,
        tax_regime: str,
        target_date: date | None = None,
    ) -> ReportTemplateVersion | None:
        """Get the active template version for a report code + regime."""
        pool = await get_pool()
        if target_date is None:
            target_date = date.today()

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT t.code, t.name, t.tax_regime,
                          tv.id, tv.template_id, tv.version, tv.status,
                          tv.effective_from, tv.effective_to, tv.checksum,
                          tv.schema_version, tv.origin, tv.locale,
                          tv.fields_json, tv.formulas_json, tv.control_ratios
                   FROM accounting.report_template t
                   JOIN accounting.report_template_version tv ON tv.template_id = t.id
                   WHERE t.code = $1
                     AND t.tax_regime = $2
                     AND tv.status = 'active'
                     AND tv.effective_from <= $3
                     AND (tv.effective_to IS NULL OR tv.effective_to >= $3)
                   ORDER BY tv.effective_from DESC
                   LIMIT 1""",
                template_code,
                tax_regime,
                target_date,
            )
            if not row:
                return None

            return ReportTemplateVersion(
                id=str(row["id"]),
                template_id=str(row["template_id"]),
                code=row["code"],
                name=row["name"],
                version=row["version"],
                status=row["status"],
                tax_regime=row["tax_regime"],
                effective_from=row["effective_from"],
                effective_to=row["effective_to"],
                checksum=row["checksum"],
                schema_version=row["schema_version"],
                origin=row["origin"],
                locale=row["locale"],
                fields=json.loads(row["fields_json"]) if isinstance(row["fields_json"], str) else (row["fields_json"] or {}),
                formulas=json.loads(row["formulas_json"]) if isinstance(row["formulas_json"], str) else (row["formulas_json"] or {}),
                control_ratios=json.loads(row["control_ratios"]) if isinstance(row["control_ratios"], str) else (row["control_ratios"] or []),
            )

    @staticmethod
    async def create_or_update(
        code: str,
        name: str,
        tax_regime: str,
        version: str,
        effective_from: date,
        effective_to: date | None = None,
        fields: dict | None = None,
        formulas: dict | None = None,
        control_ratios: list | None = None,
        origin: str = "nalog.ru",
    ) -> str:
        """Create or update a template version. Idempotent."""
        pool = await get_pool()

        # Compute checksum
        checksum_input = json.dumps({
            "code": code, "version": version, "fields": fields or {},
            "formulas": formulas or {}, "control_ratios": control_ratios or [],
        }, sort_keys=True, ensure_ascii=False).encode()
        checksum = hashlib.sha256(checksum_input).hexdigest()

        async with pool.acquire() as conn:
            # Upsert template
            tpl = await conn.fetchrow(
                "SELECT id FROM accounting.report_template WHERE code = $1",
                code,
            )
            if tpl:
                template_id = str(tpl["id"])
            else:
                template_id = str(uuid.uuid4())
                await conn.execute(
                    "INSERT INTO accounting.report_template (id, code, name, tax_regime, is_active) "
                    "VALUES ($1, $2, $3, $4, true)",
                    template_id, code, name, tax_regime,
                )

            # Check existing version
            existing = await conn.fetchrow(
                "SELECT id FROM accounting.report_template_version "
                "WHERE template_id = $1 AND version = $2",
                template_id, version,
            )
            if existing:
                return str(existing["id"])

            # Create version
            tv_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO accounting.report_template_version
                   (id, template_id, version, status, effective_from, effective_to,
                    checksum, schema_version, origin, locale,
                    fields_json, formulas_json, control_ratios)
                   VALUES ($1, $2, $3, 'fetched', $4, $5, $6,
                           '1.0', $7, 'ru_RU', $8::jsonb, $9::jsonb, $10::jsonb)""",
                tv_id, template_id, version, effective_from, effective_to,
                checksum, origin,
                json.dumps(fields or {}),
                json.dumps(formulas or {}),
                json.dumps(control_ratios or []),
            )
            return tv_id

    @staticmethod
    async def activate(template_code: str, version: str) -> bool:
        """Activate a template version. Previous active → deprecated."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            tv = await conn.fetchrow(
                """SELECT tv.id FROM accounting.report_template_version tv
                   JOIN accounting.report_template t ON t.id = tv.template_id
                   WHERE t.code = $1 AND tv.version = $2""",
                template_code, version,
            )
            if not tv:
                return False

            # Deprecate current active
            await conn.execute(
                """UPDATE accounting.report_template_version
                   SET status = 'deprecated'
                   WHERE template_id = (SELECT id FROM accounting.report_template WHERE code = $1)
                     AND status = 'active'""",
                template_code,
            )

            # Activate new
            await conn.execute(
                "UPDATE accounting.report_template_version SET status = 'active' WHERE id = $1",
                str(tv["id"]),
            )
            return True

    @staticmethod
    async def seed_default_templates() -> dict[str, str]:
        """Seed default report templates for all regimes. Idempotent."""
        result = {}

        # USN_D declaration
        result["USN_DECLARATION"] = await TemplateProvider.create_or_update(
            code="USN_DECLARATION",
            name="USN Tax Declaration (Income)",
            tax_regime="USN_D",
            version="2026.01",
            effective_from=date(2026, 1, 1),
            fields={
                "section_1": {"type": "section", "label": "Сумма налога"},
                "section_1.line_010": {"type": "amount", "label": "Доходы (код 010)", "source": "KUDIR_INCOME.total"},
                "section_1.line_020": {"type": "amount", "label": "Налоговая база (код 020)"},
                "section_1.line_030": {"type": "amount", "label": "Сумма налога (код 030)"},
                "section_2": {"type": "section", "label": "Реквизиты"},
                "section_2.inn": {"type": "string", "label": "ИНН"},
                "section_2.kpp": {"type": "string", "label": "КПП"},
            },
            formulas={
                "section_1.line_020": "section_1.line_010",  # same as income
                "section_1.line_030": "section_1.line_020 * 0.06",  # 6% rate
            },
            control_ratios=["section_1.line_030 >= 0"],
        )

        # USN_DR declaration
        result["USN_DR_DECLARATION"] = await TemplateProvider.create_or_update(
            code="USN_DR_DECLARATION",
            name="USN Tax Declaration (Income minus Expenses)",
            tax_regime="USN_DR",
            version="2026.01",
            effective_from=date(2026, 1, 1),
            fields={
                "section_1": {"type": "section", "label": "Доходы и расходы"},
                "section_1.line_010": {"type": "amount", "label": "Доходы (код 010)", "source": "KUDIR_INCOME.total"},
                "section_1.line_020": {"type": "amount", "label": "Расходы (код 020)", "source": "KUDIR_EXPENSE.total"},
                "section_1.line_030": {"type": "amount", "label": "Налоговая база (код 030)"},
                "section_1.line_040": {"type": "amount", "label": "Сумма налога (код 040)"},
            },
            formulas={
                "section_1.line_030": "section_1.line_010 - section_1.line_020",
                "section_1.line_040": "section_1.line_030 * 0.15",
            },
            control_ratios=["section_1.line_030 >= 0", "section_1.line_040 >= 0"],
        )

        # VAT return
        result["VAT_3"] = await TemplateProvider.create_or_update(
            code="VAT_3",
            name="VAT Return (Section 3)",
            tax_regime="GENERAL",
            version="2026.01",
            effective_from=date(2026, 1, 1),
            fields={
                "section_3": {"type": "section", "label": "Расчёт налога"},
                "section_3.line_010": {"type": "amount", "label": "Налоговая база по реализации", "source": "GENERAL_INCOME.total"},
                "section_3.line_020": {"type": "amount", "label": "Сумма НДС (код 020)"},
                "section_3.line_030": {"type": "amount", "label": "Налоговые вычеты", "source": "VAT_PURCHASE.total"},
                "section_3.line_040": {"type": "amount", "label": "Итого НДС к уплате (код 040)"},
            },
            formulas={
                "section_3.line_020": "section_3.line_010 * 0.20",
                "section_3.line_040": "section_3.line_020 - section_3.line_030",
            },
            control_ratios=["section_3.line_040 >= 0"],
        )

        # Activate all
        for code in result:
            await TemplateProvider.activate(code, "2026.01")

        return result
