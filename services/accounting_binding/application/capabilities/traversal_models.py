"""
Knowledge Graph Traversal v1 — domain contract: traversal models.

Pure dataclasses. No Platform imports. No business logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TraversalNode:
    """A node discovered during graph traversal."""
    node_type: str
    domain_id: str
    label: str = ""
    display_name: str = ""


@dataclass(frozen=True)
class TraversalEdge:
    """An edge traversed between two nodes."""
    source_type: str
    source_domain: str
    edge_type: str
    target_type: str
    target_domain: str


@dataclass(frozen=True)
class TraversalQuery:
    """Request to traverse the Knowledge Graph (1-hop).

    Start from either a logical entity (node_type + domain_id)
    or from a specific revision (revision_id).
    """
    node_type: str | None = None
    domain_id: str | None = None
    revision_id: str | None = None
    limit: int = 50


@dataclass(frozen=True)
class TraversalResult:
    """Result of a 1-hop graph traversal.

    Root + all directly connected nodes + edges connecting them.
    """
    root: TraversalNode | None = None
    nodes: tuple[TraversalNode, ...] = ()
    edges: tuple[TraversalEdge, ...] = ()
    revision_ids: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return self.root is None
