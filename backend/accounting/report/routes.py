"""Report API routes for Phase 5."""

from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from backend.accounting.db.pool import get_pool
from backend.accounting.models.enums import ReportStatus, TemplateStatus
from backend.accounting.report.template import TemplateProvider, ReportTemplateVersion
from backend.accounting.report.generator import ReportGenerator, ReportDraft, ReportCell
from backend.accounting.report.audit import AuditEngine, AuditResult, AuditFinding
from backend.accounting.report.submission import SubmissionService

router = APIRouter(prefix="/reports", tags=["Reports"])


# ── Templates ──────────────────────────────────────────────────────────


@router.get("/templates")
async def list_templates(
    tax_regime: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List report templates with versions."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        where = ["1=1"]
        params = []
        idx = 1
        if tax_regime:
            where.append(f"t.tax_regime = ${idx}")
            params.append(tax_regime)
            idx += 1

        w = " AND ".join(where)
        total = await conn.fetchval(
            f"SELECT count(*) FROM accounting.report_template t WHERE {w}",
            *params,
        )
        rows = await conn.fetch(
            f"""SELECT t.id, t.code, t.name, t.tax_regime, t.is_active,
                      tv.id AS version_id, tv.version, tv.status,
                      tv.effective_from, tv.effective_to, tv.checksum,
                      tv.schema_version, tv.origin
               FROM accounting.report_template t
               LEFT JOIN accounting.report_template_version tv ON tv.template_id = t.id
               WHERE {w}
               ORDER BY t.code, tv.effective_from DESC
               LIMIT ${idx} OFFSET ${idx+1}""",
            *params, limit, offset,
        )

        templates = {}
        for r in rows:
            pid = str(r["id"])
            if pid not in templates:
                templates[pid] = {
                    "id": pid,
                    "code": r["code"],
                    "name": r["name"],
                    "tax_regime": r["tax_regime"],
                    "is_active": r["is_active"],
                    "versions": [],
                }
            if r["version_id"]:
                templates[pid]["versions"].append({
                    "id": str(r["version_id"]),
                    "version": r["version"],
                    "status": r["status"],
                    "effective_from": str(r["effective_from"]),
                    "effective_to": str(r["effective_to"]) if r["effective_to"] else None,
                    "checksum": r["checksum"],
                    "origin": r["origin"],
                })

        return {"total": total, "items": list(templates.values())}


@router.post("/templates/seed")
async def seed_templates():
    """Seed default report templates. Idempotent."""
    result = await TemplateProvider.seed_default_templates()
    return {"seeded": list(result.keys())}


# ── Generate ───────────────────────────────────────────────────────────


@router.post("/generate")
async def generate_report(body: dict):
    """Generate a report draft from tax registers and template.

    Deterministic: same inputs → same report_hash.
    """
    company_id = body.get("company_id")
    template_code = body.get("template_code")
    tax_period_id = body.get("tax_period_id")

    if not company_id or not template_code:
        raise HTTPException(status_code=400, detail="company_id and template_code required")

    pool = await get_pool()

    # Get company's tax regime
    async with pool.acquire() as conn:
        regime_row = await conn.fetchrow(
            "SELECT regime_type FROM accounting.tax_regime WHERE company_id = $1 AND is_active = true",
            company_id,
        )
    if not regime_row:
        raise HTTPException(status_code=400, detail="No active tax regime for company")

    # Map regime to report regime code
    regime_map = {
        "usn_income": "USN_D",
        "usn_income_expense": "USN_DR",
        "osno": "GENERAL",
    }
    tax_regime = regime_map.get(regime_row["regime_type"], "USN_D")

    # Get active template
    template = await TemplateProvider.get_active(template_code, tax_regime)
    if not template:
        raise HTTPException(status_code=404, detail=f"No active template found for {template_code} / {tax_regime}")

    # Generate
    draft = await ReportGenerator.generate(
        company_id=company_id,
        template_version=template,
        tax_period_id=tax_period_id,
    )

    # Save
    report_id = await ReportGenerator.save(draft)

    return {
        "report_id": report_id,
        "report_version": draft.report_version,
        "report_hash": draft.report_hash,
        "template_version": template.version,
        "cells_count": len(draft.cells),
        "total_income": draft.total_income,
        "total_expense": draft.total_expense,
        "total_tax": draft.total_tax,
    }


# ── Reports CRUD ───────────────────────────────────────────────────────


@router.get("")
async def list_reports(
    company_id: str | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List reports with filters."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        where = ["1=1"]
        params = []
        idx = 1
        if company_id:
            where.append(f"company_id = ${idx}")
            params.append(company_id)
            idx += 1
        if status:
            where.append(f"status = ${idx}")
            params.append(status)
            idx += 1

        w = " AND ".join(where)
        total = await conn.fetchval(
            f"SELECT count(*) FROM accounting.report_draft WHERE {w}",
            *params,
        )
        rows = await conn.fetch(
            f"""SELECT id, report_version, company_id, template_version_id,
                      tax_policy_version, tax_period_id, status, report_hash,
                      generated_at, total_income, total_expense, total_tax
               FROM accounting.report_draft
               WHERE {w}
               ORDER BY generated_at DESC
               LIMIT ${idx} OFFSET ${idx+1}""",
            *params, limit, offset,
        )
        return {"total": total, "items": [dict(r) for r in rows]}


@router.get("/{report_id}")
async def get_report(report_id: str):
    """Get a report with all its cells."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        report = await conn.fetchrow(
            "SELECT * FROM accounting.report_draft WHERE id = $1",
            report_id,
        )
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        cells = await conn.fetch(
            "SELECT * FROM accounting.report_cell WHERE report_id = $1 ORDER BY cell_code",
            report_id,
        )

        return {
            "report": dict(report),
            "cells": [dict(c) for c in cells],
        }


# ── Status / Approve / Submit ──────────────────────────────────────────


@router.post("/{report_id}/validate")
async def validate_report(report_id: str):
    """Validate a report — run control ratios and formal checks."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        report = await conn.fetchrow(
            "SELECT * FROM accounting.report_draft WHERE id = $1",
            report_id,
        )
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        if report["status"] not in ("draft",):
            raise HTTPException(status_code=400, detail=f"Invalid status for validation: {report['status']}")

        # Run a quick validation check (without full AI audit)
        # Check: all cells have values
        cells = await conn.fetch(
            "SELECT count(*) as cnt FROM accounting.report_cell WHERE report_id = $1 AND value IS NULL AND value_numeric IS NULL",
            report_id,
        )
        empty_cells = cells[0]["cnt"] if cells else 0

        if empty_cells > 0:
            raise HTTPException(status_code=400, detail=f"Report has {empty_cells} empty cells")

        # Check: template version is active
        tv = await conn.fetchrow(
            "SELECT status FROM accounting.report_template_version WHERE id = $1",
            report["template_version_id"],
        )
        if tv and tv["status"] not in ("active", "deprecated"):
            raise HTTPException(status_code=400, detail=f"Template version status is {tv['status']}")

        await conn.execute(
            "UPDATE accounting.report_draft SET status = 'validated', updated_at = now() WHERE id = $1",
            report_id,
        )

    return {"status": "validated", "report_id": report_id}


@router.post("/{report_id}/audit")
async def audit_report(report_id: str):
    """Run AI audit on a report. Read-only — does not affect report content.

    Multi-pass: formal → logical → contextual → cross_check.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        report = await conn.fetchrow(
            "SELECT * FROM accounting.report_draft WHERE id = $1",
            report_id,
        )
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

    result = await AuditEngine.audit(report_id)
    result_id = await AuditEngine.save(result)

    return {
        "audit_result_id": result_id,
        "audit_model_version": result.audit_model_version,
        "risk_score": result.risk_score,
        "approved": result.approved,
        "findings_count": len(result.findings),
        "findings": [
            {
                "severity": f.severity,
                "category": f.category,
                "field_path": f.field_path,
                "description": f.description,
                "suggested_action": f.suggested_action,
            }
            for f in result.findings
        ],
    }


@router.post("/{report_id}/approve")
async def approve_report(report_id: str):
    """Approve a report (accountant action). AI cannot do this."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        report = await conn.fetchrow(
            "SELECT * FROM accounting.report_draft WHERE id = $1",
            report_id,
        )
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        if report["status"] not in ("ai_reviewed", "validated"):
            raise HTTPException(status_code=400,
                                detail=f"Cannot approve: status is {report['status']}. Must be ai_reviewed.")

        await conn.execute(
            "UPDATE accounting.report_draft SET status = 'accountant_approved', updated_at = now() WHERE id = $1",
            report_id,
        )

    return {"status": "accountant_approved", "report_id": report_id}


@router.post("/{report_id}/submit")
async def submit_report(report_id: str):
    """Submit a report (creates submission package)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        report = await conn.fetchrow(
            "SELECT * FROM accounting.report_draft WHERE id = $1",
            report_id,
        )
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        if report["status"] not in ("accountant_approved", "ready_to_submit"):
            raise HTTPException(status_code=400,
                                detail=f"Cannot submit: status is {report['status']}. Must be accountant_approved.")

    package = await SubmissionService.create(report_id)

    return {
        "submission_id": package.submission_id,
        "report_id": package.report_id,
        "report_version": package.report_version,
        "transport_payload_hash": package.transport_payload_hash,
    }


# ── Audit Log ──────────────────────────────────────────────────────────


@router.get("/{report_id}/audit-log")
async def get_audit_log(report_id: str):
    """Get all audit results for a report."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        results = await conn.fetch(
            """SELECT ar.id, ar.audit_model_version, ar.risk_score, ar.approved,
                      ar.supersedes, ar.created_at,
                      af.severity, af.category, af.field_path, af.description,
                      af.evidence, af.suggested_action
               FROM accounting.report_audit_result ar
               LEFT JOIN accounting.report_audit_finding af ON af.audit_result_id = ar.id
               WHERE ar.report_id = $1
               ORDER BY ar.created_at DESC, af.created_at""",
            report_id,
        )

        # Group by audit result
        grouped = {}
        for r in results:
            rid = str(r["id"])
            if rid not in grouped:
                grouped[rid] = {
                    "id": rid,
                    "audit_model_version": r["audit_model_version"],
                    "risk_score": float(r["risk_score"]),
                    "approved": r["approved"],
                    "supersedes": str(r["supersedes"]) if r["supersedes"] else None,
                    "created_at": str(r["created_at"]),
                    "findings": [],
                }
            if r["severity"]:
                grouped[rid]["findings"].append({
                    "severity": r["severity"],
                    "category": r["category"],
                    "field_path": r["field_path"],
                    "description": r["description"],
                    "evidence": r["evidence"],
                    "suggested_action": r["suggested_action"],
                })

        return {"total": len(grouped), "items": list(grouped.values())}


# ── Determinism Check ──────────────────────────────────────────────────


@router.get("/{report_id}/hash")
async def get_report_hash(report_id: str):
    """Get the deterministic hash for a report."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        report = await conn.fetchrow(
            "SELECT id, report_hash, report_version, status FROM accounting.report_draft WHERE id = $1",
            report_id,
        )
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        return {
            "report_id": str(report["id"]),
            "report_hash": report["report_hash"],
            "report_version": report["report_version"],
            "status": report["status"],
        }


# ── Lifecycle Transition ───────────────────────────────────────────────


@router.post("/{report_id}/ready-to-submit")
async def ready_to_submit(report_id: str):
    """Mark report as ready to submit."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        report = await conn.fetchrow(
            "SELECT * FROM accounting.report_draft WHERE id = $1",
            report_id,
        )
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        if report["status"] != "accountant_approved":
            raise HTTPException(status_code=400,
                                detail=f"Cannot mark ready: status is {report['status']}")

        await conn.execute(
            "UPDATE accounting.report_draft SET status = 'ready_to_submit', updated_at = now() WHERE id = $1",
            report_id,
        )

    return {"status": "ready_to_submit", "report_id": report_id}
