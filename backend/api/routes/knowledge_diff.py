"""Knowledge Diff API — Capability поверх Platform v2.3.1.

Endpoints:
  GET /knowledge/revisions/{left}/diff/{right}  — diff between two revisions

Reuses existing diff engine from application.capabilities.knowledge_diff.
No Platform changes.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId
from domain.business_relationship.kg_node import GraphNode

from application.capabilities.knowledge_diff import diff_snapshots, NodeDiffEntry
from application.capabilities.knowledge_diff import (
    NodeChange as DCNodeChange,
)

router = APIRouter(prefix="/knowledge", tags=["Knowledge Diff"])


def _get_integrator(request: Request):
    integrator = getattr(request.app.state, "integrator", None)
    if integrator is None:
        raise HTTPException(status_code=503, detail="Knowledge Runtime not available")
    return integrator


def _build_node_key_resolver(
    left_nodes: tuple[GraphNode, ...],
    right_nodes: tuple[GraphNode, ...],
) -> callable:
    """Build a resolver: node_id (uuid) → (node_type_str, domain_id).

    Combines nodes from both snapshots so edge comparisons can resolve
    node references regardless of which snapshot they're in.
    """
    mapping: dict[str, tuple[str, str]] = {}
    for n in list(left_nodes) + list(right_nodes):
        nt = n.node_type.value if hasattr(n.node_type, "value") else str(n.node_type)
        mapping[n.node_id.value] = (nt, n.domain_id)
    return lambda node_id: mapping.get(node_id, ("", node_id))


def _serialize_diff(result) -> dict:
    """Convert DiffResult to JSON-serializable dict."""
    return {
        "nodes": {
            "added": [
                {"node_type": e.node_type, "domain_id": e.domain_id}
                for e in result.nodes if e.status == "added"
            ],
            "removed": [
                {"node_type": e.node_type, "domain_id": e.domain_id}
                for e in result.nodes if e.status == "removed"
            ],
            "updated": [
                {
                    "node_type": e.node_type,
                    "domain_id": e.domain_id,
                    "changes": [
                        {"field": c.field, "old_value": _v(c.old_value), "new_value": _v(c.new_value)}
                        for c in e.changes
                    ],
                }
                for e in result.nodes if e.status == "updated"
            ],
        },
        "edges": {
            "added": [
                {
                    "source_type": e.source_type,
                    "source_domain": e.source_domain,
                    "edge_type": e.edge_type,
                    "target_type": e.target_type,
                    "target_domain": e.target_domain,
                }
                for e in result.edges if e.status == "added"
            ],
            "removed": [
                {
                    "source_type": e.source_type,
                    "source_domain": e.source_domain,
                    "edge_type": e.edge_type,
                    "target_type": e.target_type,
                    "target_domain": e.target_domain,
                }
                for e in result.edges if e.status == "removed"
            ],
        },
        "provenance": {
            "added": [
                {"source_type": e.source_type, "source_id": e.source_id, "description": e.description}
                for e in result.provenance if e.status == "added"
            ],
            "removed": [
                {"source_type": e.source_type, "source_id": e.source_id, "description": e.description}
                for e in result.provenance if e.status == "removed"
            ],
        },
        "explanation": {
            "added": [
                {"step_number": e.step_number, "summary": e.summary}
                for e in result.explanation if e.status == "added"
            ],
            "removed": [
                {"step_number": e.step_number, "summary": e.summary}
                for e in result.explanation if e.status == "removed"
            ],
            "changed": [
                {
                    "step_number": e.step_number,
                    "summary": e.summary,
                    "changes": [
                        {"field": c.field, "old_value": _v(c.old_value), "new_value": _v(c.new_value)}
                        for c in e.changes
                    ],
                }
                for e in result.explanation if e.status == "changed"
            ],
        },
        "summary": {
            "nodes_added": sum(1 for e in result.nodes if e.status == "added"),
            "nodes_removed": sum(1 for e in result.nodes if e.status == "removed"),
            "nodes_updated": sum(1 for e in result.nodes if e.status == "updated"),
            "edges_added": sum(1 for e in result.edges if e.status == "added"),
            "edges_removed": sum(1 for e in result.edges if e.status == "removed"),
            "provenance_added": sum(1 for e in result.provenance if e.status == "added"),
            "provenance_removed": sum(1 for e in result.provenance if e.status == "removed"),
            "explanation_added": sum(1 for e in result.explanation if e.status == "added"),
            "explanation_removed": sum(1 for e in result.explanation if e.status == "removed"),
            "explanation_changed": sum(1 for e in result.explanation if e.status == "changed"),
        },
    }


def _v(val) -> str | None:
    """Convert field value to string for serialization."""
    if val is None:
        return None
    if isinstance(val, (tuple, list)):
        return ", ".join(str(v) for v in val)
    return str(val)


@router.get("/revisions/{left_revision_id}/diff/{right_revision_id}")
async def get_revision_diff(
    left_revision_id: str,
    right_revision_id: str,
    request: Request,
):
    """Compute the diff between two KnowledgeRevisions.

    Reads both revisions from the Repository, extracts their
    KnowledgeSnapshots, and delegates to the stateless Diff Engine.

    Returns empty diff if left == right (by contract).
    """
    integrator = _get_integrator(request)
    repo = integrator.revision_repository

    from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId

    left_record = repo.get(KnowledgeRevisionId(value=left_revision_id))
    if left_record is None:
        raise HTTPException(status_code=404, detail=f"Left revision not found: {left_revision_id}")

    right_record = repo.get(KnowledgeRevisionId(value=right_revision_id))
    if right_record is None:
        raise HTTPException(status_code=404, detail=f"Right revision not found: {right_revision_id}")

    left_snapshot = left_record.revision.snapshot
    right_snapshot = right_record.revision.snapshot

    # Build node key resolver from both snapshots for edge comparison
    resolver = _build_node_key_resolver(
        left_snapshot.graph.nodes if left_snapshot else (),
        right_snapshot.graph.nodes if right_snapshot else (),
    )

    result = diff_snapshots(left_snapshot, right_snapshot, resolve_node_key=resolver)

    return _serialize_diff(result)
