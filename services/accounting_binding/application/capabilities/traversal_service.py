"""
Knowledge Graph Traversal v1 — traversal service.

Stateless. Walks the KnowledgeGraph 1-hop from a start node.
Uses logical identity (node_type, domain_id) — same contract as Diff.
No Platform changes.
"""
from __future__ import annotations

from typing import Any

from domain.business_relationship.knowledge_snapshot import KnowledgeSnapshot
from domain.business_relationship.kg_graph import KnowledgeGraph
from domain.business_relationship.kg_node import GraphNode
from domain.business_relationship.kg_edge import GraphEdge
from domain.business_relationship.kg_enums import GraphNodeType, GraphEdgeType

from application.capabilities.traversal_models import (
    TraversalNode,
    TraversalEdge,
    TraversalQuery,
    TraversalResult,
)


class KnowledgeGraphTraversalService:
    """Stateless graph traversal service.

    Takes a KnowledgeSnapshot and a start node identifier.
    Returns 1-hop neighbourhood within that snapshot's graph.
    """

    @staticmethod
    def traverse(
        snapshot: KnowledgeSnapshot,
        query: TraversalQuery,
    ) -> TraversalResult:
        """Traverse 1-hop from the start node within the given snapshot."""
        graph = snapshot.graph

        # Build index: node_id (uuid) → (node_type, domain_id, label, display_name)
        node_id_to_logical: dict[str, tuple[str, str, str, str]] = {}
        logical_to_node_ids: dict[tuple[str, str], list[str]] = {}

        for node in graph.nodes:
            nt = node.node_type.value if isinstance(node.node_type, GraphNodeType) else str(node.node_type)
            key = (nt, node.domain_id)
            nid = node.node_id.value
            node_id_to_logical[nid] = (nt, node.domain_id, node.attributes.label, node.attributes.display_name)
            if key not in logical_to_node_ids:
                logical_to_node_ids[key] = []
            logical_to_node_ids[key].append(nid)

        # Find the start node
        if query.node_type and query.domain_id:
            start_key = (query.node_type, query.domain_id)
            start_node_ids = logical_to_node_ids.get(start_key, [])
            if not start_node_ids:
                return TraversalResult()  # empty
            start_node_data = node_id_to_logical.get(start_node_ids[0])
            if not start_node_data:
                return TraversalResult()
            root = TraversalNode(
                node_type=start_node_data[0],
                domain_id=start_node_data[1],
                label=start_node_data[2],
                display_name=start_node_data[3],
            )
        elif query.revision_id:
            # Start from the revision itself — collect all entities as root nodes
            return KnowledgeGraphTraversalService._traverse_from_revision(
                snapshot, query, node_id_to_logical, logical_to_node_ids,
            )
        else:
            return TraversalResult()

        # 1-hop edge walk
        traversed_nodes: dict[tuple[str, str], TraversalNode] = {}
        traversed_edges: list[TraversalEdge] = []

        target_ids = set(start_node_ids)
        visited_logical: set[tuple[str, str]] = {start_key}

        for edge in graph.edges:
            src_id = edge.source_node.value
            tgt_id = edge.target_node.value

            # Check if this edge connects TO or FROM any start node
            is_outgoing = src_id in target_ids
            is_incoming = tgt_id in target_ids

            if not (is_outgoing or is_incoming):
                continue

            # Determine other end
            other_id = tgt_id if is_outgoing else src_id
            other_data = node_id_to_logical.get(other_id)
            if not other_data:
                continue

            other_key = (other_data[0], other_data[1])
            if other_key in visited_logical:
                continue
            visited_logical.add(other_key)

            et = edge.edge_type.value if isinstance(edge.edge_type, GraphEdgeType) else str(edge.edge_type)

            if is_outgoing:
                te = TraversalEdge(
                    source_type=start_node_data[0], source_domain=start_node_data[1],
                    edge_type=et,
                    target_type=other_data[0], target_domain=other_data[1],
                )
            else:
                te = TraversalEdge(
                    source_type=other_data[0], source_domain=other_data[1],
                    edge_type=et,
                    target_type=start_node_data[0], target_domain=start_node_data[1],
                )

            traversed_edges.append(te)
            traversed_nodes[other_key] = TraversalNode(
                node_type=other_data[0], domain_id=other_data[1],
                label=other_data[2], display_name=other_data[3],
            )

        # Sort for determinism
        sorted_nodes = tuple(
            sorted(traversed_nodes.values(), key=lambda n: (n.node_type, n.domain_id))
        )
        sorted_edges = tuple(
            sorted(traversed_edges, key=lambda e: (e.source_type, e.source_domain, e.edge_type))
        )

        return TraversalResult(
            root=root,
            nodes=sorted_nodes,
            edges=sorted_edges,
        )

    @staticmethod
    def _traverse_from_revision(
        snapshot: KnowledgeSnapshot,
        query: TraversalQuery,
        node_id_to_logical: dict[str, tuple[str, str, str, str]],
        logical_to_node_ids: dict[tuple[str, str], list[str]],
    ) -> TraversalResult:
        """Traverse from all entities in a revision."""
        if not snapshot.graph.nodes:
            return TraversalResult()

        # First entity as root
        first = snapshot.graph.nodes[0]
        nt = first.node_type.value if isinstance(first.node_type, GraphNodeType) else str(first.node_type)
        root = TraversalNode(
            node_type=nt, domain_id=first.domain_id,
            label=first.attributes.label, display_name=first.attributes.display_name,
        )

        # Collect all logical keys
        all_nodes: dict[tuple[str, str], TraversalNode] = {}
        all_edges: list[TraversalEdge] = []

        for edge in snapshot.graph.edges:
            src_id = edge.source_node.value
            tgt_id = edge.target_node.value
            src_data = node_id_to_logical.get(src_id)
            tgt_data = node_id_to_logical.get(tgt_id)
            if not src_data or not tgt_data:
                continue

            et = edge.edge_type.value if isinstance(edge.edge_type, GraphEdgeType) else str(edge.edge_type)
            sk = (src_data[0], src_data[1])
            tk = (tgt_data[0], tgt_data[1])

            all_nodes[sk] = TraversalNode(
                node_type=src_data[0], domain_id=src_data[1],
                label=src_data[2], display_name=src_data[3],
            )
            all_nodes[tk] = TraversalNode(
                node_type=tgt_data[0], domain_id=tgt_data[1],
                label=tgt_data[2], display_name=tgt_data[3],
            )
            all_edges.append(TraversalEdge(
                source_type=src_data[0], source_domain=src_data[1],
                edge_type=et,
                target_type=tgt_data[0], target_domain=tgt_data[1],
            ))

        # Remove root from neighbours (root is reported separately)
        root_key = (root.node_type, root.domain_id)
        all_nodes.pop(root_key, None)

        sorted_nodes = tuple(
            sorted(all_nodes.values(), key=lambda n: (n.node_type, n.domain_id))
        )
        sorted_edges = tuple(
            sorted(all_edges, key=lambda e: (e.source_type, e.source_domain, e.edge_type))
        )

        return TraversalResult(
            root=root,
            nodes=sorted_nodes,
            edges=sorted_edges,
        )
