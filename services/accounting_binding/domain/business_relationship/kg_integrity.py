"""
GraphIntegrityChecker + GraphIntegrityReport — structural validation.

Read-only. NO fixing. NO mutation.
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.business_relationship.kg_graph import KnowledgeGraph


@dataclass(frozen=True)
class GraphIntegrityReport:
    """Отчёт о целостности графа. Immutable."""
    is_valid: bool = True
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class GraphIntegrityChecker:
    """Проверяет структурную целостность графа.

    Read-only. NO mutation. NO fixing.
    """

    @staticmethod
    def check(graph: KnowledgeGraph) -> GraphIntegrityReport:
        """Проверить граф на структурные проблемы."""
        errors: list[str] = []
        warnings: list[str] = []

        node_ids = {n.node_id for n in graph.nodes}
        edge_ids = set()

        # Check duplicate node IDs
        if len(node_ids) != len(graph.nodes):
            all_ids = [n.node_id for n in graph.nodes]
            seen = set()
            for nid in all_ids:
                if nid in seen:
                    errors.append(f"Duplicate node ID: {nid}")
                seen.add(nid)

        # Check edges
        for edge in graph.edges:
            # Duplicate edge IDs
            if edge.edge_id in edge_ids:
                errors.append(f"Duplicate edge ID: {edge.edge_id}")
            edge_ids.add(edge.edge_id)

            # Missing source node
            if edge.source_node not in node_ids:
                errors.append(f"Edge {edge.edge_id}: source node {edge.source_node} not found")

            # Missing target node
            if edge.target_node not in node_ids:
                errors.append(f"Edge {edge.edge_id}: target node {edge.target_node} not found")

            # Self-loop
            if edge.source_node == edge.target_node:
                warnings.append(f"Edge {edge.edge_id}: self-loop (source == target)")

        # Orphan edges warning
        if graph.edges and not graph.nodes:
            warnings.append(f"Graph has {len(graph.edges)} edges but no nodes")

        return GraphIntegrityReport(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )
