"""
Graph versioning, diff, and snapshot.

GraphVersion — immutable version marker.
GraphDiff — computed difference between two graphs.
GraphSnapshot — serializable representation for audit/replay.

All immutable. NO DB writes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class GraphVersion:
    """Immutable version of a KnowledgeGraph."""
    version: int
    knowledge_version: int = 1
    node_count: int = 0
    edge_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class GraphMetrics:
    """Structural metrics of a graph."""
    node_count: int = 0
    edge_count: int = 0
    component_count: int = 0
    average_degree: float = 0.0
    density: float = 0.0
    diameter: int = 0  # longest shortest path

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def summary(self) -> str:
        return (
            f"Metrics(nodes={self.node_count}, edges={self.edge_count}, "
            f"components={self.component_count}, avg_deg={self.average_degree:.1f}, "
            f"density={self.density:.4f}, diameter={self.diameter})"
        )


@dataclass
class GraphDiff:
    """Difference between two KnowledgeGraphs. Not a graph — pure data."""
    version_from: int = 0
    version_to: int = 0
    added_nodes: list[str] = field(default_factory=list)
    removed_nodes: list[str] = field(default_factory=list)
    added_edges: list[tuple[str, str, str]] = field(default_factory=list)  # (source, target, type)
    removed_edges: list[tuple[str, str, str]] = field(default_factory=list)
    changed_weights: list[tuple[str, float, float]] = field(default_factory=list)  # (edge_id, old, new)
    changed_metadata: list[tuple[str, str]] = field(default_factory=list)  # (node_id, field)

    @classmethod
    def compare(cls, old_graph, new_graph) -> GraphDiff:
        """Compute difference between two KnowledgeGraph instances."""
        from domain.business_relationship.knowledge_graph import KnowledgeGraph

        old_nodes = set(old_graph._nodes.keys())
        new_nodes = set(new_graph._nodes.keys())

        diff = cls(
            version_from=getattr(old_graph, 'graph_version', None).version if hasattr(old_graph, 'graph_version') and old_graph.graph_version else 0,
            version_to=getattr(new_graph, 'graph_version', None).version if hasattr(new_graph, 'graph_version') and new_graph.graph_version else 0,
            added_nodes=list(new_nodes - old_nodes),
            removed_nodes=list(old_nodes - new_nodes),
        )

        # Edge diff by (source, target, type)
        old_edge_keys = {(e.source_id, e.target_id, e.edge_type.value) for e in old_graph._edges}
        new_edge_keys = {(e.source_id, e.target_id, e.edge_type.value) for e in new_graph._edges}
        diff.added_edges = list(new_edge_keys - old_edge_keys)
        diff.removed_edges = list(old_edge_keys - new_edge_keys)

        # Weight changes
        old_weights = {e.id: e.weight for e in old_graph._edges}
        new_weights = {e.id: e.weight for e in new_graph._edges}
        for eid, w in new_weights.items():
            if eid in old_weights and old_weights[eid] != w:
                diff.changed_weights.append((eid, old_weights[eid], w))

        return diff

    @property
    def has_changes(self) -> bool:
        return bool(self.added_nodes or self.removed_nodes or self.added_edges or
                    self.removed_edges or self.changed_weights)

    @property
    def summary(self) -> str:
        return (
            f"Diff(v{self.version_from}→v{self.version_to}): "
            f"+{len(self.added_nodes)}n -{len(self.removed_nodes)}n "
            f"+{len(self.added_edges)}e -{len(self.removed_edges)}e"
        )


@dataclass
class GraphSnapshot:
    """Serializable representation of a graph at a point in time.

    For: audit, replay, comparison, debugging.
    NOT a storage mechanism.
    """
    document_id: str = ""
    graph_version: int = 0
    knowledge_version: int = 1
    created_at: datetime = field(default_factory=datetime.utcnow)
    serialized_graph: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_graph(cls, graph, document_id: str = "", knowledge_version: int = 1) -> GraphSnapshot:
        """Create snapshot from KnowledgeGraph."""
        from domain.business_relationship.knowledge_graph import KnowledgeGraph

        # Serialize nodes
        nodes = {}
        for nid, node in graph._nodes.items():
            nodes[nid] = {
                "id": node.node_id,
                "type": node.node_type.value,
                "label": node.label,
                "domain_id": node.domain_object_id,
            }

        # Serialize edges
        edges = []
        for e in graph._edges:
            edges.append({
                "id": e.id,
                "source": e.source_id,
                "target": e.target_id,
                "type": e.edge_type.value,
                "weight": e.weight,
                "confidence": e.confidence,
                "document_id": e.document_id,
                "provenance": e.provenance,
            })

        version = getattr(graph, 'graph_version', None)
        ver = version.version if version else 0

        return cls(
            document_id=document_id,
            graph_version=ver,
            knowledge_version=knowledge_version,
            serialized_graph={"nodes": nodes, "edges": edges},
        )

    def to_json(self) -> str:
        return json.dumps({
            "document_id": self.document_id,
            "graph_version": self.graph_version,
            "knowledge_version": self.knowledge_version,
            "created_at": self.created_at.isoformat(),
            "graph": self.serialized_graph,
        }, ensure_ascii=False, default=str)
