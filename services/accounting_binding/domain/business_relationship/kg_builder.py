"""
GraphBuilder — coordinator of graph construction.

Stateless. Deterministic. Creates a new KnowledgeGraph each call.
NO mutation of existing Graph. NO traversal. NO navigation.
"""
from __future__ import annotations

from domain.business_relationship.kg_graph import KnowledgeGraph
from domain.business_relationship.kg_node import GraphNode
from domain.business_relationship.kg_edge import GraphEdge
from domain.business_relationship.kg_identifiers import GraphNodeId
from domain.business_relationship.kg_build_result import GraphBuildResult, GraphBuildReport
from domain.business_relationship.kg_node_factory import GraphNodeFactory
from domain.business_relationship.kg_edge_factory import GraphEdgeFactory
from domain.business_relationship.kg_integrity import GraphIntegrityChecker
from domain.business_relationship.canonical_entity import CanonicalEntity
from domain.business_relationship.agreement import Agreement
from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.fact_types import FactType


class GraphBuilder:
    """Строит новый KnowledgeGraph из доменных объектов.

    Stateless. Deterministic. Каждый вызов — новый граф.
    """

    def __init__(self):
        self._node_factory = GraphNodeFactory()
        self._edge_factory = GraphEdgeFactory()
        self._integrity_checker = GraphIntegrityChecker()

    def build(
        self,
        entities: list[CanonicalEntity],
        agreements: list[Agreement],
        facts: list[BusinessFact],
    ) -> GraphBuildResult:
        """Build new KnowledgeGraph from domain objects."""
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        domain_to_graph: dict[str, GraphNodeId] = {}
        warnings: list[str] = []

        # 1. Create nodes from entities
        for entity in entities:
            node = self._node_factory.create_entity_node(
                domain_id=str(entity.id),
                display_name=entity.display_name,
            )
            nodes.append(node)
            domain_to_graph[str(entity.id)] = node.node_id

        # 2. Create nodes from agreements
        for agreement in agreements:
            node = self._node_factory.create_agreement_node(
                domain_id=str(agreement.id),
                display_name=agreement.number,
            )
            nodes.append(node)
            domain_to_graph[str(agreement.id)] = node.node_id

        # 3. Create edges from facts (entity → fact)
        for fact in facts:
            fact_node = self._node_factory.create_fact_node(
                domain_id=str(fact.id),
                display_name=fact.fact_type.value,
            )
            nodes.append(fact_node)
            domain_to_graph[str(fact.id)] = fact_node.node_id

            # Link entity → fact
            if fact.subject_entity_id in domain_to_graph:
                edges.append(self._edge_factory.create_has_fact(
                    domain_to_graph[fact.subject_entity_id],
                    fact_node.node_id,
                ))

        # 4. Edge: entity ↔ agreement
        for agreement in agreements:
            ag_id = str(agreement.id)
            if ag_id in domain_to_graph:
                for participant in agreement.participants:
                    participant_id = str(participant.entity_id)
                    if participant_id in domain_to_graph:
                        edges.append(self._edge_factory.create_participates(
                            domain_to_graph[participant_id],
                            domain_to_graph[ag_id],
                        ))

        # 5. Build immutable graph
        graph = KnowledgeGraph(
            nodes=tuple(nodes),
            edges=tuple(edges),
        )

        # 6. Integrity check
        report = self._integrity_checker.check(graph)
        if report.errors:
            for err in report.errors:
                warnings.append(err)

        return GraphBuildResult(
            graph=graph,
            warnings=tuple(warnings),
        )
