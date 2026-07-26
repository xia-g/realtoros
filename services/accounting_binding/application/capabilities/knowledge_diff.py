"""
Knowledge Diff Explorer — T1: stateless diff logic.

Pure functions over immutable Domain models.
Zero changes to Domain, Repository, Persistence, or any Platform component.

Identity contract:
  Node key:   (node_type, domain_id)
  Edge key:   ((source_type, source_domain), edge_type, (target_type, target_domain))
  Provenance: (source_type, source_id)
  Explanation step: step_number
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domain.business_relationship.knowledge_snapshot import KnowledgeSnapshot
from domain.business_relationship.kg_node import GraphNode
from domain.business_relationship.kg_edge import GraphEdge
from domain.business_relationship.kg_enums import GraphNodeType, GraphEdgeType
from domain.business_relationship.kg_provenance_link import ProvenanceLink
from domain.business_relationship.ke_explanation_step import ExplanationStep
from domain.business_relationship.ke_explanation_parts import ExplanationReason, ExplanationEvidence


# ─── Diff DTOs ──────────────────────────────────────────────────


@dataclass(frozen=True)
class NodeChange:
    """A single changed field in a node."""
    field: str
    old_value: Any = ""
    new_value: Any = ""


@dataclass(frozen=True)
class NodeDiffEntry:
    """A node that was added, removed, or updated."""
    node_type: str
    domain_id: str
    status: str  # "added" | "removed" | "updated"
    changes: tuple[NodeChange, ...] = ()


@dataclass(frozen=True)
class EdgeDiffEntry:
    """An edge that was added or removed."""
    source_type: str
    source_domain: str
    edge_type: str
    target_type: str
    target_domain: str
    status: str  # "added" | "removed"


@dataclass(frozen=True)
class ProvenanceDiffEntry:
    """A provenance link that was added or removed."""
    source_type: str
    source_id: str
    description: str
    status: str  # "added" | "removed"


@dataclass(frozen=True)
class ExplanationDiffEntry:
    """An explanation step that was added, removed, or changed."""
    step_number: int
    status: str  # "added" | "removed" | "changed"
    summary: str = ""
    changes: tuple[NodeChange, ...] = ()


@dataclass(frozen=True)
class DiffResult:
    """Immutable result of comparing two KnowledgeSnapshots.

    Invariants:
      - Diff(A, A) → empty
      - Deterministic: same inputs → same output
      - Order-independent: (A, B) == (B, A) with reversed signs
    """
    left_revision_id: str = ""
    right_revision_id: str = ""
    nodes: tuple[NodeDiffEntry, ...] = ()
    edges: tuple[EdgeDiffEntry, ...] = ()
    provenance: tuple[ProvenanceDiffEntry, ...] = ()
    explanation: tuple[ExplanationDiffEntry, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (self.nodes or self.edges or self.provenance or self.explanation)


# ─── Helpers ────────────────────────────────────────────────────


def _node_key(node: GraphNode) -> tuple[str, str]:
    """Logical identity for a graph node."""
    nt = node.node_type.value if isinstance(node.node_type, GraphNodeType) else str(node.node_type)
    return (nt, node.domain_id)


def _edge_key(edge: GraphEdge) -> tuple[tuple[str, str], str, tuple[str, str]]:
    """Semantic key for an edge: (source_key, edge_type, target_key).

    edge_id (random UUID) is NOT used.
    """
    # Source key — extract from GraphNodeId.value if it matches a node.
    # Since edge stores source_node and target_node as GraphNodeId (uuid),
    # we derive the semantic key from attributes or metadata.
    # For diff purposes we use (source_node.value, edge_type, target_node.value)
    # but those are random UUIDs. We need to match edges by their domain_key.
    # Since the edge only stores node_id references, not domain_ids,
    # we rely on the caller to resolve domain keys before calling diff_edges.
    et = edge.edge_type.value if isinstance(edge.edge_type, GraphEdgeType) else str(edge.edge_type)
    src = edge.source_node.value
    tgt = edge.target_node.value
    return (("", src), et, ("", tgt))


def _link_key(link: ProvenanceLink) -> tuple[str, str]:
    """Identity for a provenance link."""
    st = link.source.source_type.value if hasattr(link.source.source_type, "value") else str(link.source.source_type)
    return (st, link.source.source_id)


def _step_fields(step: ExplanationStep) -> dict[str, Any]:
    """Serializable representation of an explanation step for comparison."""
    return {
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
    }


def _node_payload(node: GraphNode) -> dict[str, Any]:
    """Fields considered for 'updated' detection.

    Excludes: node_id (random), metadata (service), provenance (service).
    """
    return {
        "node_type": node.node_type.value if isinstance(node.node_type, GraphNodeType) else str(node.node_type),
        "domain_id": node.domain_id,
        "label": node.attributes.label,
        "display_name": node.attributes.display_name,
        "tags": tuple(node.attributes.tags),
        "properties": tuple(node.attributes.properties),
    }


def _payload_diff(old: dict[str, Any], new: dict[str, Any]) -> tuple[NodeChange, ...]:
    """Compute field-level changes between two payload dicts."""
    changes: list[NodeChange] = []
    for key in set(list(old.keys()) + list(new.keys())):
        if key not in new:
            changes.append(NodeChange(field=key, old_value=old[key], new_value=None))
        elif key not in old:
            changes.append(NodeChange(field=key, old_value=None, new_value=new[key]))
        elif old[key] != new[key]:
            changes.append(NodeChange(field=key, old_value=old[key], new_value=new[key]))
    return tuple(changes)


# ─── Core diff functions ────────────────────────────────────────


def diff_nodes(
    left_nodes: tuple[GraphNode, ...],
    right_nodes: tuple[GraphNode, ...],
) -> tuple[NodeDiffEntry, ...]:
    """Compute node diff between two collections of GraphNodes.

    Algorithm:
      1. Index both sides by logical key (node_type, domain_id)
      2. Keys in right but not left → added
      3. Keys in left but not right → removed
      4. Keys in both → compare payload → updated or unchanged
    """
    left_index: dict[tuple[str, str], GraphNode] = {}
    for n in left_nodes:
        left_index[_node_key(n)] = n

    right_index: dict[tuple[str, str], GraphNode] = {}
    for n in right_nodes:
        right_index[_node_key(n)] = n

    result: list[NodeDiffEntry] = []

    # Added: in right, not in left
    for key, node in right_index.items():
        if key not in left_index:
            nt, did = key
            result.append(NodeDiffEntry(
                node_type=nt, domain_id=did, status="added",
            ))

    # Removed: in left, not in right
    for key, node in left_index.items():
        if key not in right_index:
            nt, did = key
            result.append(NodeDiffEntry(
                node_type=nt, domain_id=did, status="removed",
            ))

    # Updated: in both, payload differs
    for key in left_index:
        if key in right_index:
            old_p = _node_payload(left_index[key])
            new_p = _node_payload(right_index[key])
            changes = _payload_diff(old_p, new_p)
            if changes:
                nt, did = key
                result.append(NodeDiffEntry(
                    node_type=nt, domain_id=did, status="updated",
                    changes=changes,
                ))

    # Stable order: sort by (node_type, domain_id)
    result.sort(key=lambda e: (e.node_type, e.domain_id))
    return tuple(result)


def diff_edges(
    left_edges: tuple[GraphEdge, ...],
    right_edges: tuple[GraphEdge, ...],
    resolve_node_key: callable | None = None,
) -> tuple[EdgeDiffEntry, ...]:
    """Compute edge diff between two collections of GraphEdges.

    Edges are compared by semantic key derived from node domain keys.
    If resolve_node_key is provided, it maps node_id → (node_type, domain_id).
    Otherwise, edge comparison falls back to the raw node_id values
    (which are random UUIDs and will always differ between revisions).

    Note: For correct diff, callers MUST provide resolve_node_key that maps
    both source_node and target_node to their (node_type, domain_id) pairs.
    """
    def _default_key(edge: GraphEdge) -> tuple[str, str, str]:
        et = edge.edge_type.value if isinstance(edge.edge_type, GraphEdgeType) else str(edge.edge_type)
        return (edge.source_node.value, et, edge.target_node.value)

    def _semantic_key(edge: GraphEdge) -> tuple[str, str, str]:
        et = edge.edge_type.value if isinstance(edge.edge_type, GraphEdgeType) else str(edge.edge_type)
        if resolve_node_key:
            sk_type, sk_domain = resolve_node_key(edge.source_node.value)
            tk_type, tk_domain = resolve_node_key(edge.target_node.value)
            return (f"{sk_type}:{sk_domain}", et, f"{tk_type}:{tk_domain}")
        return _default_key(edge)

    left_set = {_semantic_key(e) for e in left_edges}
    right_set = {_semantic_key(e) for e in right_edges}

    result: list[EdgeDiffEntry] = []

    for e in right_edges:
        k = _semantic_key(e)
        if k not in left_set:
            et = e.edge_type.value if isinstance(e.edge_type, GraphEdgeType) else str(e.edge_type)
            src_part, _, tgt_part = k
            src_type, src_domain = src_part.split(":", 1) if ":" in src_part else ("", src_part)
            tgt_type, tgt_domain = tgt_part.split(":", 1) if ":" in tgt_part else ("", tgt_part)
            result.append(EdgeDiffEntry(
                source_type=src_type, source_domain=src_domain,
                edge_type=et,
                target_type=tgt_type, target_domain=tgt_domain,
                status="added",
            ))

    for e in left_edges:
        k = _semantic_key(e)
        if k not in right_set:
            et = e.edge_type.value if isinstance(e.edge_type, GraphEdgeType) else str(e.edge_type)
            src_part, _, tgt_part = k
            src_type, src_domain = src_part.split(":", 1) if ":" in src_part else ("", src_part)
            tgt_type, tgt_domain = tgt_part.split(":", 1) if ":" in tgt_part else ("", tgt_part)
            result.append(EdgeDiffEntry(
                source_type=src_type, source_domain=src_domain,
                edge_type=et,
                target_type=tgt_type, target_domain=tgt_domain,
                status="removed",
            ))

    result.sort(key=lambda e: (e.source_type, e.source_domain, e.edge_type))
    return tuple(result)


def diff_provenance(
    left_prov: tuple[ProvenanceLink, ...],
    right_prov: tuple[ProvenanceLink, ...],
) -> tuple[ProvenanceDiffEntry, ...]:
    """Compute provenance diff between two collections of links."""
    left_index = {_link_key(link) for link in left_prov}
    right_index = {_link_key(link) for link in right_prov}

    result: list[ProvenanceDiffEntry] = []

    for link in right_prov:
        k = _link_key(link)
        if k not in left_index:
            st, sid = k
            result.append(ProvenanceDiffEntry(
                source_type=st, source_id=sid,
                description=link.source.description,
                status="added",
            ))

    for link in left_prov:
        k = _link_key(link)
        if k not in right_index:
            st, sid = k
            result.append(ProvenanceDiffEntry(
                source_type=st, source_id=sid,
                description=link.source.description,
                status="removed",
            ))

    result.sort(key=lambda e: (e.source_type, e.source_id))
    return tuple(result)


def diff_explanation(
    left_steps: tuple[ExplanationStep, ...],
    right_steps: tuple[ExplanationStep, ...],
) -> tuple[ExplanationDiffEntry, ...]:
    """Compute explanation step diff between two collections."""
    left_index = {s.step_number: s for s in left_steps}
    right_index = {s.step_number: s for s in right_steps}

    result: list[ExplanationDiffEntry] = []

    for sn in sorted(right_index):
        if sn not in left_index:
            step = right_index[sn]
            result.append(ExplanationDiffEntry(
                step_number=sn, status="added",
                summary=step.summary,
            ))

    for sn in sorted(left_index):
        if sn not in right_index:
            step = left_index[sn]
            result.append(ExplanationDiffEntry(
                step_number=sn, status="removed",
                summary=step.summary,
            ))

    for sn in sorted(left_index):
        if sn in right_index:
            old_f = _step_fields(left_index[sn])
            new_f = _step_fields(right_index[sn])
            changes = _payload_diff(old_f, new_f)
            if changes:
                result.append(ExplanationDiffEntry(
                    step_number=sn, status="changed",
                    summary=right_index[sn].summary,
                    changes=changes,
                ))

    result.sort(key=lambda e: e.step_number)
    return tuple(result)


# ─── High-level API ─────────────────────────────────────────────


def diff_snapshots(
    left: KnowledgeSnapshot,
    right: KnowledgeSnapshot,
    resolve_node_key: callable | None = None,
) -> DiffResult:
    """Compute the full diff between two KnowledgeSnapshots.

    Pure function. Neither snapshot is modified.

    Args:
        left: The older / left snapshot
        right: The newer / right snapshot
        resolve_node_key: Optional callable(node_id_str) → (node_type, domain_id)
                          for resolving edge node references to semantic keys.
                          If None, edges are compared by raw node_id (not recommended).
    """
    node_result = diff_nodes(left.graph.nodes, right.graph.nodes)

    edge_result = diff_edges(left.graph.edges, right.graph.edges, resolve_node_key)

    prov_links_left = tuple(left.provenance.chain.links) if left.provenance else ()
    prov_links_right = tuple(right.provenance.chain.links) if right.provenance else ()
    prov_result = diff_provenance(prov_links_left, prov_links_right)

    exp_steps_left = tuple(left.explanation.steps) if left.explanation else ()
    exp_steps_right = tuple(right.explanation.steps) if right.explanation else ()
    exp_result = diff_explanation(exp_steps_left, exp_steps_right)

    return DiffResult(
        nodes=node_result,
        edges=edge_result,
        provenance=prov_result,
        explanation=exp_result,
    )
