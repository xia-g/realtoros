"""
GraphNodeFactory — creates individual GraphNode instances.

Stateless. Deterministic. NO knowledge of the full graph.
"""
from __future__ import annotations

from domain.business_relationship.kg_identifiers import GraphNodeId
from domain.business_relationship.kg_enums import GraphNodeType
from domain.business_relationship.kg_attributes import GraphAttributes
from domain.business_relationship.kg_node import GraphNode


class GraphNodeFactory:
    """Создаёт узлы графа. Не знает о KnowledgeGraph."""

    @staticmethod
    def create_entity_node(domain_id: str, display_name: str = "") -> GraphNode:
        return GraphNode(
            node_id=GraphNodeId.generate(),
            node_type=GraphNodeType.ENTITY,
            domain_id=domain_id,
            attributes=GraphAttributes(display_name=display_name, label=display_name or domain_id),
        )

    @staticmethod
    def create_property_node(domain_id: str, display_name: str = "") -> GraphNode:
        return GraphNode(
            node_id=GraphNodeId.generate(),
            node_type=GraphNodeType.PROPERTY,
            domain_id=domain_id,
            attributes=GraphAttributes(display_name=display_name, label=display_name or domain_id),
        )

    @staticmethod
    def create_agreement_node(domain_id: str, display_name: str = "") -> GraphNode:
        return GraphNode(
            node_id=GraphNodeId.generate(),
            node_type=GraphNodeType.AGREEMENT,
            domain_id=domain_id,
            attributes=GraphAttributes(display_name=display_name, label=display_name or domain_id),
        )

    @staticmethod
    def create_document_node(domain_id: str, display_name: str = "") -> GraphNode:
        return GraphNode(
            node_id=GraphNodeId.generate(),
            node_type=GraphNodeType.DOCUMENT,
            domain_id=domain_id,
            attributes=GraphAttributes(display_name=display_name, label=display_name or domain_id),
        )

    @staticmethod
    def create_fact_node(domain_id: str, display_name: str = "") -> GraphNode:
        return GraphNode(
            node_id=GraphNodeId.generate(),
            node_type=GraphNodeType.FACT,
            domain_id=domain_id,
            attributes=GraphAttributes(display_name=display_name, label=display_name or domain_id),
        )

    @staticmethod
    def create_deal_node(domain_id: str, display_name: str = "") -> GraphNode:
        return GraphNode(
            node_id=GraphNodeId.generate(),
            node_type=GraphNodeType.DEAL,
            domain_id=domain_id,
            attributes=GraphAttributes(display_name=display_name, label=display_name or domain_id),
        )

    @staticmethod
    def create_person_node(domain_id: str, display_name: str = "") -> GraphNode:
        return GraphNode(
            node_id=GraphNodeId.generate(),
            node_type=GraphNodeType.PERSON,
            domain_id=domain_id,
            attributes=GraphAttributes(display_name=display_name, label=display_name or domain_id),
        )
