"""MCP deal governance tools — P5.5 Deal Governance Foundation.

Provides:
- check_deal_completeness: assess a deal against its checklist + document requirements
- validate_document_package: check which required docs are missing
- get_regulation: search regulations by query and trust level
"""

from __future__ import annotations

import json
from uuid import UUID

from backend.services.compliance_service import ComplianceService
from backend.services.regulation_service import RegulationService
from backend.services.risk_assessment_service import RiskAssessmentService
from backend.services.workflow_service import WorkflowService
from backend.services.regulation_sync_service import RegulationSyncService

_compliance = ComplianceService()
_regulation_svc = RegulationService()
_risk_svc = RiskAssessmentService()
_reg_sync = RegulationSyncService()


def check_deal_completeness(
    deal_id: str,
    deal_type: str = "SALE_APARTMENT",
    completed_checkpoints: list[str] | None = None,
    uploaded_documents: list[str] | None = None,
) -> str:
    """Check a deal's compliance completeness.

    Args:
        deal_id: UUID of the deal
        deal_type: SALE_APARTMENT, MORTGAGE, or RENT
        completed_checkpoints: list of completed checkpoint keys
        uploaded_documents: list of uploaded document types

    Returns:
        JSON string with compliance score, missing items, stage summary
    """
    import asyncio

    result = asyncio.run(
        _compliance.check_deal_completeness(
            deal_id=UUID(deal_id),
            deal_type=deal_type,
            completed_checkpoints=completed_checkpoints or [],
            uploaded_documents=uploaded_documents or [],
        )
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


def validate_document_package(deal_type: str, uploaded_documents: list[str]) -> str:
    """Validate a document package for a deal type.

    Args:
        deal_type: SALE_APARTMENT, MORTGAGE, or RENT
        uploaded_documents: list of uploaded document types

    Returns:
        JSON with completeness %, missing required docs, missing recommended docs
    """
    import asyncio

    result = asyncio.run(
        _compliance.validate_document_package(
            deal_type=deal_type,
            uploaded=uploaded_documents,
        )
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


def get_regulation(query: str, min_trust: str = "COMMUNITY", limit: int = 5) -> str:
    """Search regulations by query.

    Args:
        query: search text
        min_trust: minimum trust level (OFFICIAL > VERIFIED > COMMUNITY > LLM_GENERATED)
        limit: max results

    Returns:
        JSON list of matching regulations
    """
    import asyncio

    results = asyncio.run(
        _regulation_svc.search_regulations(query=query, min_trust=min_trust, limit=limit)
    )
    return json.dumps(results, ensure_ascii=False, indent=2)


# ─── Sprint 5 Deal Copilot Tools ──────────────────────────


def check_deal_status(deal_id: str, deal_type: str = "SALE_APARTMENT") -> str:
    """Check overall deal status: workflow stage + compliance + risk."""
    import asyncio

    completeness = asyncio.run(
        _compliance.check_deal_completeness(
            deal_id=UUID(deal_id) if deal_id else UUID(int=0),
            deal_type=deal_type,
        )
    )

    risk = asyncio.run(
        _risk_svc.evaluate_deal(
            deal_id=UUID(deal_id) if deal_id else UUID(int=0),
        )
    )

    return json.dumps({
        "compliance": completeness,
        "risk": risk,
    }, ensure_ascii=False, indent=2)


def check_deal_risks(deal_id: str) -> str:
    """Assess deal risks: ownership, minors, mortgage, restrictions."""
    import asyncio

    result = asyncio.run(
        _risk_svc.evaluate_deal(
            deal_id=UUID(deal_id) if deal_id else UUID(int=0),
        )
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


def get_regulation_updates(source: str = "", since_days: int = 7) -> str:
    """Get recent regulation updates from official sources.

    Args:
        source: Росреестр, ФНС, Минфин, Правительство РФ, Госдума
        since_days: look back period in days
    """
    import asyncio

    sources = [source] if source else RegulationSyncService.SOURCES
    results = []
    for s in sources:
        r = asyncio.run(_reg_sync.fetch_updates(s))
        results.append(r)
    return json.dumps({"updates": results, "since_days": since_days}, ensure_ascii=False, indent=2)


def get_next_actions(deal_id: str, deal_type: str = "SALE_APARTMENT") -> str:
    """Get recommended next actions for a deal based on compliance gaps.

    Args:
        deal_id: UUID of the deal
        deal_type: SALE_APARTMENT, MORTGAGE, or RENT
    """
    import asyncio

    completeness = asyncio.run(
        _compliance.check_deal_completeness(
            deal_id=UUID(deal_id) if deal_id else UUID(int=0),
            deal_type=deal_type,
        )
    )

    report = asyncio.run(
        _compliance.generate_compliance_report(
            deal_id=UUID(deal_id) if deal_id else UUID(int=0),
            deal_type=deal_type,
        )
    )

    risk = asyncio.run(
        _risk_svc.evaluate_deal(
            deal_id=UUID(deal_id) if deal_id else UUID(int=0),
        )
    )

    missing = completeness.get("missing_items", [])
    next_actions = []
    for item in missing:
        next_actions.append(f"Загрузить {item['label']}")
    if risk.get("risk_level") in ("HIGH", "CRITICAL"):
        next_actions.insert(0, f"Требуется юр. проверка ({risk.get('risk_level')})")

    estimated_days = max(len(missing), 1) + (3 if risk.get("risk_level") == "HIGH" else 1)

    return json.dumps({
        "deal_id": deal_id,
        "compliance_score": completeness.get("compliance_score", 0),
        "risk_level": risk.get("risk_level", "LOW"),
        "missing_items": [i.get("label") for i in missing],
        "next_actions": next_actions,
        "estimated_completion_days": estimated_days,
    }, ensure_ascii=False, indent=2)
