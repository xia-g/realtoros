"""Knowledge Search API — Capability поверх Platform v2.3.1.

Endpoints:
  GET /knowledge/search  — поиск KnowledgeRevision

Следует стилю Explorer / Timeline / Diff API.
No Platform changes.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request

from application.capabilities.search_models import KnowledgeSearchQuery
from application.capabilities.search_service import KnowledgeSearchService

router = APIRouter(prefix="/knowledge", tags=["Knowledge Search"])


def _serialize(result) -> dict:
    """Convert KnowledgeSearchResult to JSON-safe dict."""
    return {
        "items": [
            {
                "revision_id": item.revision_id,
                "revision_number": item.revision_number,
                "source_document_id": item.source_document_id,
                "created_at": item.created_at,
                "reason": item.reason,
                "created_by": item.created_by,
            }
            for item in result.items
        ],
        "next_cursor": result.next_cursor,
        "total_matches": result.total_matches,
    }


@router.get("/search")
async def search_knowledge(
    request: Request,
    source_document_id: str = Query(None, description="Filter by source document ID"),
    reason_contains: str = Query(None, description="ILKE substring match on reason"),
    created_by: str = Query(None, description="Exact match on created_by"),
    created_after: str = Query(None, description="ISO timestamp, inclusive"),
    created_before: str = Query(None, description="ISO timestamp, inclusive"),
    revision_number_min: int = Query(None, ge=1),
    revision_number_max: int = Query(None, ge=1),
    cursor: str = Query(None, description="Cursor from previous page"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_field: str = Query("created_at", pattern="^(created_at|revision_number)$"),
    sort_direction: str = Query("DESC", pattern="^(ASC|DESC)$"),
):
    """Search KnowledgeRevision deterministically.

    All filters are AND-combined. Results sorted by created_at DESC
    (tiebreaker: revision_id DESC). Cursor-based pagination.
    """
    # Validate timestamps
    ca = cb = None
    if created_after:
        try:
            ca = datetime.fromisoformat(created_after)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid created_after format (use ISO timestamp)")

    if created_before:
        try:
            cb = datetime.fromisoformat(created_before)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid created_before format (use ISO timestamp)")

    if ca and cb and ca > cb:
        raise HTTPException(status_code=400, detail="created_after must be before created_before")

    query = KnowledgeSearchQuery(
        source_document_id=source_document_id,
        reason_contains=reason_contains,
        created_by=created_by,
        created_after=ca,
        created_before=cb,
        revision_number_min=revision_number_min,
        revision_number_max=revision_number_max,
        cursor=cursor,
        limit=limit,
        sort_field=sort_field,
        sort_direction=sort_direction,
    )

    from backend.config import settings

    service = KnowledgeSearchService(dsn=settings.DATABASE_SYNC_URL)
    result = service.search(query)

    return _serialize(result)
