"""Agent tool definitions — wrappers around existing services for ToolRegistry.

Each tool wrapper takes simple serializable parameters and returns a dict/string.
Wrappers must never raise — they return {"success": bool, "result": str, "error": str}.
"""

from __future__ import annotations

import json
from uuid import UUID

from backend.services.compliance_service import ComplianceService
from backend.services.regulation_service import RegulationService

_compliance = ComplianceService()
_regulation = RegulationService()


async def agent_check_deal_completeness(
    deal_id: str = "",
    deal_type: str = "SALE_APARTMENT",
    completed_checkpoints: str = "",
    uploaded_documents: str = "",
) -> dict:
    """Check deal completeness and return compliance score.

    Args:
        deal_id: UUID сделки
        deal_type: SALE_APARTMENT | MORTGAGE | RENT
        completed_checkpoints: comma-separated checkpoint keys
        uploaded_documents: comma-separated document types
    """
    try:
        cps = [c.strip() for c in completed_checkpoints.split(",") if c.strip()] if completed_checkpoints else []
        docs = [d.strip() for d in uploaded_documents.split(",") if d.strip()] if uploaded_documents else []

        result = await _compliance.check_deal_completeness(
            deal_id=UUID(deal_id) if deal_id else UUID(int=0),
            deal_type=deal_type,
            completed_checkpoints=cps,
            uploaded_documents=docs,
        )
        return {"success": True, "result": json.dumps(result, ensure_ascii=False), "error": ""}
    except Exception as e:
        return {"success": False, "result": "", "error": str(e)}


async def agent_validate_document_package(deal_type: str = "SALE_APARTMENT", uploaded_documents: str = "") -> dict:
    """Validate document package for a deal type.

    Args:
        deal_type: SALE_APARTMENT | MORTGAGE | RENT
        uploaded_documents: comma-separated document types
    """
    try:
        docs = [d.strip() for d in uploaded_documents.split(",") if d.strip()] if uploaded_documents else []
        result = await _compliance.validate_document_package(deal_type=deal_type, uploaded=docs)
        return {"success": True, "result": json.dumps(result, ensure_ascii=False), "error": ""}
    except Exception as e:
        return {"success": False, "result": "", "error": str(e)}


async def agent_get_regulation(query: str = "", min_trust: str = "COMMUNITY", limit: int = 5) -> dict:
    """Search regulations by query.

    Args:
        query: search text
        min_trust: OFFICIAL | VERIFIED | COMMUNITY | LLM_GENERATED
        limit: max results
    """
    try:
        results = await _regulation.search_regulations(query=query, min_trust=min_trust, limit=limit)
        return {"success": True, "result": json.dumps(results, ensure_ascii=False), "error": ""}
    except Exception as e:
        return {"success": False, "result": "", "error": str(e)}


async def agent_search_client(query: str = "") -> dict:
    """Search clients by name or contact.

    Args:
        query: search text (name, phone, email)
    """
    return {
        "success": True,
        "result": json.dumps({"message": "Search clients — stub. Integrate with ClientService after Sprint 3."}, ensure_ascii=False),
        "error": "",
    }


async def agent_search_property(query: str = "") -> dict:
    """Search properties by address or title.

    Args:
        query: search text
    """
    return {
        "success": True,
        "result": json.dumps({"message": "Search properties — stub. Integrate with PropertyService after Sprint 3."}, ensure_ascii=False),
        "error": "",
    }


async def agent_search_deal(query: str = "") -> dict:
    """Search deals by title or client.

    Args:
        query: search text
    """
    return {
        "success": True,
        "result": json.dumps({"message": "Search deals — stub. Integrate with DealService after Sprint 3."}, ensure_ascii=False),
        "error": "",
    }
