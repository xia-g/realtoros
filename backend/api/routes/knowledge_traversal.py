"""Knowledge Graph Traversal API — Capability поверх Platform v2.3.1.

Endpoints:
  GET /knowledge/traversal — 1-hop graph traversal

Следует стилю Explorer / Timeline / Diff / Search API.
No Platform changes.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId

from application.capabilities.traversal_models import TraversalQuery
from application.capabilities.traversal_service import KnowledgeGraphTraversalService

router = APIRouter(prefix="/knowledge", tags=["Knowledge Traversal"])


def _get_integrator(request: Request):
    integrator = getattr(request.app.state, "integrator", None)
    if integrator is None:
        raise HTTPException(status_code=503, detail="Knowledge Runtime not available")
    return integrator


def _serialize(result) -> dict:
    """Convert TraversalResult to JSON."""
    if result.is_empty:
        return {"root": None, "nodes": [], "edges": [], "revision_ids": []}

    return {
        "root": {
            "node_type": result.root.node_type,
            "domain_id": result.root.domain_id,
            "label": result.root.label,
        },
        "nodes": [
            {
                "node_type": n.node_type,
                "domain_id": n.domain_id,
                "label": n.label,
            }
            for n in result.nodes
        ],
        "edges": [
            {
                "source_type": e.source_type,
                "source_domain": e.source_domain,
                "edge_type": e.edge_type,
                "target_type": e.target_type,
                "target_domain": e.target_domain,
            }
            for e in result.edges
        ],
        "revision_ids": list(result.revision_ids),
    }


@router.get("/traversal")
async def traverse_graph(
    request: Request,
    node_type: str = Query(None, description="Node type (e.g. entity, agreement)"),
    domain_id: str = Query(None, description="Domain ID of the start node"),
    revision_id: str = Query(None, description="Start from all entities in this revision"),
    limit: int = Query(50, ge=1, le=200),
):
    """Traverse the Knowledge Graph 1-hop from a start node.

    Start by either:
      - node_type + domain_id (logical entity)
      - revision_id (all entities in that revision)

    Returns root node + directly connected nodes + edges.
    """
    integrator = _get_integrator(request)
    repo = integrator.revision_repository

    query = TraversalQuery(
        node_type=node_type,
        domain_id=domain_id,
        revision_id=revision_id,
        limit=limit,
    )

    # Validate: need either (node_type + domain_id) or revision_id
    if not (revision_id or (node_type and domain_id)):
        raise HTTPException(
            status_code=400,
            detail="Provide either (node_type + domain_id) or revision_id",
        )

    if revision_id:
        record = repo.get(KnowledgeRevisionId(value=revision_id))
        if record is None:
            raise HTTPException(status_code=404, detail=f"Revision not found: {revision_id}")
        snapshot = record.revision.snapshot
    elif node_type and domain_id:
        # Try the latest revision's snapshot for entity-based traversal
        from backend.config import settings as bsettings
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(bsettings.DATABASE_SYNC_URL)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT revision_id FROM knowledge_revisions ORDER BY created_at DESC LIMIT 1")
                latest = cur.fetchone()
        finally:
            conn.close()

        if not latest:
            return {"root": None, "nodes": [], "edges": [], "revision_ids": []}

        record = repo.get(KnowledgeRevisionId(value=latest["revision_id"]))
        if record is None:
            return {"root": None, "nodes": [], "edges": [], "revision_ids": []}
        snapshot = record.revision.snapshot

        # Verify the entity exists in this snapshot
        from domain.business_relationship.kg_enums import GraphNodeType
        found = False
        for node in snapshot.graph.nodes:
            nt = node.node_type.value if isinstance(node.node_type, GraphNodeType) else str(node.node_type)
            if nt == node_type and node.domain_id == domain_id:
                found = True
                break

        if not found:
            return {"root": None, "nodes": [], "edges": [], "revision_ids": []}

    # Need a snapshot now
    service = KnowledgeGraphTraversalService()
    result = service.traverse(snapshot, query)

    return _serialize(result)
