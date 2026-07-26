"""
Knowledge Consistency Check v1 — models and stateless validation.

Pure functions over KnowledgeSnapshot.
No Platform changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domain.business_relationship.knowledge_snapshot import KnowledgeSnapshot
from domain.business_relationship.kg_node import GraphNode
from domain.business_relationship.kg_edge import GraphEdge
from domain.business_relationship.kg_enums import GraphNodeType, GraphEdgeType
from domain.business_relationship.kg_identifiers import GraphNodeId
from domain.business_relationship.kg_provenance_link import ProvenanceLink


# ─── Models ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class ConsistencyViolation:
    severity: str          # "error" | "warning"
    violation_type: str    # "broken_edge" | "orphan_node" | …
    message: str
    affected_node_type: str | None = None
    affected_domain_id: str | None = None
    affected_field: str | None = None
    expected: str | None = None
    actual: str | None = None


@dataclass(frozen=True)
class ConsistencyCheckResult:
    revision_id: str = ""
    is_consistent: bool = True
    violations: tuple[ConsistencyViolation, ...] = ()
    checked_nodes: int = 0
    checked_edges: int = 0

    @property
    def errors(self) -> int:
        return sum(1 for v in self.violations if v.severity == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for v in self.violations if v.severity == "warning")


# ─── Individual checks ────────────────────────────────────────────


def _collect_node_ids(nodes: tuple[GraphNode, ...]) -> set[str]:
    return {n.node_id.value for n in nodes}


def _collect_logical_keys(nodes: tuple[GraphNode, ...]) -> dict[tuple[str, str], list[str]]:
    keys: dict[tuple[str, str], list[str]] = {}
    for n in nodes:
        nt = n.node_type.value if isinstance(n.node_type, GraphNodeType) else str(n.node_type)
        k = (nt, n.domain_id)
        if k not in keys:
            keys[k] = []
        keys[k].append(n.node_id.value)
    return keys


def check_broken_edges(
    graph_nodes: tuple[GraphNode, ...],
    graph_edges: tuple[GraphEdge, ...],
) -> list[ConsistencyViolation]:
    """Every edge.source_node and edge.target_node must exist in nodes."""
    node_ids = _collect_node_ids(graph_nodes)
    violations: list[ConsistencyViolation] = []

    for edge in graph_edges:
        for field, nid in [("source_node", edge.source_node.value),
                           ("target_node", edge.target_node.value)]:
            if nid not in node_ids:
                violations.append(ConsistencyViolation(
                    severity="error",
                    violation_type="broken_edge",
                    message=f"Edge {edge.edge_id.value}: {field}={nid} not found in graph nodes",
                    affected_field=field,
                    expected=f"one of {len(node_ids)} existing node_ids",
                    actual=nid,
                ))
    return violations


def check_orphan_nodes(
    graph_nodes: tuple[GraphNode, ...],
    graph_edges: tuple[GraphEdge, ...],
) -> list[ConsistencyViolation]:
    """A node with no incoming or outgoing edges is an orphan."""
    connected: set[str] = set()
    for edge in graph_edges:
        connected.add(edge.source_node.value)
        connected.add(edge.target_node.value)

    violations: list[ConsistencyViolation] = []
    for node in graph_nodes:
        if node.node_id.value not in connected:
            nt = node.node_type.value if isinstance(node.node_type, GraphNodeType) else str(node.node_type)
            violations.append(ConsistencyViolation(
                severity="warning",
                violation_type="orphan_node",
                message=f"Node '{node.domain_id}' ({nt}) has no edges",
                affected_node_type=nt,
                affected_domain_id=node.domain_id,
            ))
    return violations


def check_duplicate_nodes(
    graph_nodes: tuple[GraphNode, ...],
) -> list[ConsistencyViolation]:
    """Same (node_type, domain_id) appearing more than once."""
    keys = _collect_logical_keys(graph_nodes)
    violations: list[ConsistencyViolation] = []
    for (nt, did), ids in keys.items():
        if len(ids) > 1:
            violations.append(ConsistencyViolation(
                severity="error",
                violation_type="duplicate_node",
                message=f"Logical node ({nt}, {did}) appears {len(ids)} times: {ids}",
                affected_node_type=nt,
                affected_domain_id=did,
                expected="1 node_id per logical key",
                actual=str(len(ids)),
            ))
    return violations


def check_self_references(
    graph_edges: tuple[GraphEdge, ...],
) -> list[ConsistencyViolation]:
    """Edge should not connect a node to itself."""
    violations: list[ConsistencyViolation] = []
    for edge in graph_edges:
        if edge.source_node.value == edge.target_node.value:
            violations.append(ConsistencyViolation(
                severity="warning",
                violation_type="self_reference",
                message=f"Edge {edge.edge_id.value}: source == target ({edge.source_node.value})",
                affected_field="source_node/target_node",
            ))
    return violations


def check_missing_provenance(
    graph_nodes: tuple[GraphNode, ...],
    provenance_links: tuple[ProvenanceLink, ...],
) -> list[ConsistencyViolation]:
    """Every node should have at least one provenance link."""
    linked_node_ids = {link.graph_node_id.value for link in provenance_links}
    node_ids = _collect_node_ids(graph_nodes)

    violations: list[ConsistencyViolation] = []
    for node in graph_nodes:
        if node.node_id.value not in linked_node_ids:
            nt = node.node_type.value if isinstance(node.node_type, GraphNodeType) else str(node.node_type)
            violations.append(ConsistencyViolation(
                severity="warning",
                violation_type="missing_provenance",
                message=f"Node '{node.domain_id}' ({nt}) has no provenance link",
                affected_node_type=nt,
                affected_domain_id=node.domain_id,
            ))
    return violations


def check_invalid_edge_relation(
    graph_edges: tuple[GraphEdge, ...],
) -> list[ConsistencyViolation]:
    """Check for edge types that don't match node type semantics.

    For v1: basic check that edge_type is not empty.
    Deferred: full node_type ↔ edge_type compatibility.
    """
    violations: list[ConsistencyViolation] = []
    for edge in graph_edges:
        et = edge.edge_type.value if isinstance(edge.edge_type, GraphEdgeType) else str(edge.edge_type)
        if not et or et == "":
            violations.append(ConsistencyViolation(
                severity="error",
                violation_type="invalid_relation",
                message=f"Edge {edge.edge_id.value} has empty edge_type",
            ))
    return violations


# ─── Orchestrator ─────────────────────────────────────────────────


def check_snapshot_consistency(
    snapshot: KnowledgeSnapshot,
    revision_id: str = "",
) -> ConsistencyCheckResult:
    """Run all structural consistency checks against a KnowledgeSnapshot.

    Pure function. Snapshot is not modified.
    Deterministic: same snapshot → same violations in same order.
    """
    graph = snapshot.graph
    nodes = graph.nodes
    edges = graph.edges
    provenance_links = tuple(snapshot.provenance.chain.links) if snapshot.provenance else ()

    all_violations: list[ConsistencyViolation] = []

    all_violations.extend(check_broken_edges(nodes, edges))
    all_violations.extend(check_orphan_nodes(nodes, edges))
    all_violations.extend(check_duplicate_nodes(nodes))
    all_violations.extend(check_self_references(edges))
    all_violations.extend(check_missing_provenance(nodes, provenance_links))
    all_violations.extend(check_invalid_edge_relation(edges))

    # Deterministic ordering: severity DESC (error first), then type, then domain_id
    severity_order = {"error": 0, "warning": 1}
    all_violations.sort(key=lambda v: (
        severity_order.get(v.severity, 99),
        v.violation_type,
        v.affected_node_type or "",
        v.affected_domain_id or "",
    ))

    return ConsistencyCheckResult(
        revision_id=revision_id,
        is_consistent=len(all_violations) == 0,
        violations=tuple(all_violations),
        checked_nodes=len(nodes),
        checked_edges=len(edges),
    )
