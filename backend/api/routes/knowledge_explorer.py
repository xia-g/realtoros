"""Knowledge Explorer API — Capability поверх Platform v2.3.1.

Endpoints:
  GET /knowledge/revisions                — список Revision
  GET /knowledge/revisions/{id}           — детали Revision
  GET /knowledge/revisions/{id}/graph     — Graph из snapshot
  GET /knowledge/revisions/{id}/provenance — Provenance из snapshot

Никаких изменений в Platform v2.3.1.
"""
from __future__ import annotations

import sys
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId

router = APIRouter(prefix="/knowledge", tags=["Knowledge Explorer"])


# ── Helpers ──────────────────────────────────────────────────────


def _get_integrator(request: Request):
    """Получить KnowledgeRuntimeIntegrator из app.state."""
    integrator = getattr(request.app.state, "integrator", None)
    if integrator is None:
        raise HTTPException(
            status_code=503,
            detail="Knowledge Runtime not available (app.state.integrator is None)",
        )
    return integrator


def _serialise_graph(snapshot) -> dict[str, Any]:
    """Преобразовать KnowledgeSnapshot.graph в API-ответ."""
    graph = snapshot.graph
    nodes = []
    for node in graph.nodes:
        nodes.append({
            "node_id": node.node_id.value,
            "node_type": node.node_type.value if hasattr(node.node_type, "value") else str(node.node_type),
            "domain_id": node.domain_id,
            "label": node.attributes.label if hasattr(node, "attributes") else "",
            "display_name": node.attributes.display_name if hasattr(node, "attributes") else "",
        })
    edges = []
    for edge in graph.edges:
        edges.append({
            "edge_id": edge.edge_id.value,
            "edge_type": edge.edge_type.value if hasattr(edge.edge_type, "value") else str(edge.edge_type),
            "source_node": edge.source_node.value,
            "target_node": edge.target_node.value,
            "confidence": edge.attributes.properties if hasattr(edge, "attributes") else 1.0,
        })
    return {"node_count": graph.node_count, "edge_count": graph.edge_count, "nodes": nodes, "edges": edges}


def _serialise_provenance(snapshot) -> dict[str, Any]:
    """Преобразовать KnowledgeSnapshot.provenance в API-ответ."""
    provenance = snapshot.provenance
    if provenance is None:
        return {"provenance_id": "", "links": [], "link_count": 0}
    links = []
    for link in provenance.chain.links:
        links.append({
            "graph_node_id": link.graph_node_id.value if hasattr(link.graph_node_id, "value") else str(link.graph_node_id),
            "source_type": link.source.source_type.value if hasattr(link.source.source_type, "value") else str(link.source.source_type),
            "source_id": link.source.source_id,
            "description": link.source.description,
            "confidence": link.confidence,
        })
    return {
        "provenance_id": provenance.provenance_id.value,
        "link_count": len(links),
        "links": links,
    }


def _serialise_explanation(snapshot) -> dict[str, Any]:
    """Преобразовать KnowledgeSnapshot.explanation в API-ответ."""
    explanation = snapshot.explanation
    if explanation is None:
        return {"explanation_id": "", "steps": [], "step_count": 0, "overall_confidence": 0.0}
    steps = []
    for step in explanation.steps:
        steps.append({
            "step_number": step.step_number,
            "summary": step.summary,
            "reasons": [
                {
                    "reason_type": r.reason_type.value if hasattr(r.reason_type, "value") else str(r.reason_type),
                    "summary": r.summary,
                    "confidence": r.confidence,
                }
                for r in step.reasons
            ],
            "evidence": [
                {
                    "source_type": e.source_type,
                    "source_id": e.source_id,
                    "description": e.description,
                    "confidence": e.confidence,
                }
                for e in step.evidence
            ],
        })
    return {
        "explanation_id": explanation.explanation_id.value,
        "step_count": len(steps),
        "steps": steps,
        "overall_confidence": explanation.overall_confidence,
    }


# ── Endpoints ────────────────────────────────────────────────────


@router.get("/revisions")
async def list_revisions(request: Request):
    """Список всех KnowledgeRevision.

    Читает напрямую из PostgreSQL через psycopg2 (не через Repository,
    так как Protocol не имеет метода list_all). Это API/View logic,
    а не Platform change.
    """
    integrator = _get_integrator(request)
    repo = integrator.revision_repository

    # Используем projection_store для поиска всех ProjectionId,
    # затем извлекаем соответствующие revision_id.
    # Альтернатива: прямой SQL-запрос к knowledge_revisions таблице.
    revisions = []
    try:
        store = integrator.projection_store
        all_ids = store.list_projection_ids()
        # Извлекаем revision_id из ProjectionId.value (формат: "entity-XXXX")
        # Более надёжный способ: читаем напрямую из БД
        pass
    except Exception:
        pass

    # Прямой SQL-запрос к knowledge_revisions (API layer, не Platform)
    import psycopg2
    import psycopg2.extras

    from backend.config import settings

    conn = psycopg2.connect(settings.DATABASE_SYNC_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT revision_id, revision_number, source_document_id, "
                "       created_at, metadata "
                "FROM knowledge_revisions "
                "ORDER BY created_at DESC"
            )
            rows = cur.fetchall()
            for row in rows:
                meta = row.get("metadata") or {}
                revisions.append({
                    "revision_id": row["revision_id"],
                    "revision_number": row["revision_number"],
                    "source_document_id": row["source_document_id"],
                    "created_at": str(row["created_at"]) if row.get("created_at") else None,
                    "reason": meta.get("reason", "") if isinstance(meta, dict) else "",
                })
    finally:
        conn.close()

    return {"revisions": revisions, "total": len(revisions)}


@router.get("/revisions/{revision_id}")
async def get_revision(revision_id: str, request: Request):
    """Детальная карточка Revision со snapshot summary."""
    integrator = _get_integrator(request)
    repo = integrator.revision_repository

    rid = KnowledgeRevisionId(value=revision_id)
    record = repo.get(rid)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Revision not found: {revision_id}")

    rev = record.revision
    snap = rev.snapshot
    meta = rev.metadata

    return {
        "revision_id": rev.revision_id.value,
        "revision_number": rev.revision_number.number,
        "source_document_id": record.source_document_id,
        "processing_job_id": record.processing_job_id,
        "created_at": str(record.created_at) if record.created_at else None,
        "metadata": {
            "created_by": meta.created_by,
            "reason": meta.reason,
            "document_count": meta.document_count,
            "entity_count": meta.entity_count,
        },
        "snapshot": {
            "graph": {
                "node_count": snap.graph.node_count,
                "edge_count": snap.graph.edge_count,
            },
            "provenance": {
                "link_count": len(list(snap.provenance.chain.links)) if snap.provenance else 0,
            },
            "explanation": {
                "step_count": snap.explanation.step_count if snap.explanation else 0,
            },
        },
    }


@router.get("/revisions/{revision_id}/graph")
async def get_revision_graph(revision_id: str, request: Request):
    """Полный Graph из KnowledgeSnapshot."""
    integrator = _get_integrator(request)
    repo = integrator.revision_repository

    rid = KnowledgeRevisionId(value=revision_id)
    record = repo.get(rid)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Revision not found: {revision_id}")

    graph = record.revision.snapshot.graph
    return _serialise_graph(record.revision.snapshot)


@router.get("/revisions/{revision_id}/provenance")
async def get_revision_provenance(revision_id: str, request: Request):
    """Полный Provenance из KnowledgeSnapshot."""
    integrator = _get_integrator(request)
    repo = integrator.revision_repository

    rid = KnowledgeRevisionId(value=revision_id)
    record = repo.get(rid)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Revision not found: {revision_id}")

    return _serialise_provenance(record.revision.snapshot)


@router.get("/revisions/{revision_id}/explanation")
async def get_revision_explanation(revision_id: str, request: Request):
    """Полное Explanation из KnowledgeSnapshot."""
    integrator = _get_integrator(request)
    repo = integrator.revision_repository

    rid = KnowledgeRevisionId(value=revision_id)
    record = repo.get(rid)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Revision not found: {revision_id}")

    return _serialise_explanation(record.revision.snapshot)
