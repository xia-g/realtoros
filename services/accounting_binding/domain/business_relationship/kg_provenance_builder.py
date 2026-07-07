"""
ProvenanceBuilder — coordinator of provenance construction.

Stateless. Deterministic. Creates new KnowledgeProvenance each call.
NO search. NO traversal. NO navigation. NO knowledge creation.
"""
from __future__ import annotations

from domain.business_relationship.kg_provenance_id import ProvenanceId
from domain.business_relationship.kg_provenance import KnowledgeProvenance
from domain.business_relationship.kg_provenance_chain import ProvenanceChain
from domain.business_relationship.kg_provenance_metadata import ProvenanceMetadata
from domain.business_relationship.kg_provenance_source_factory import ProvenanceSourceFactory
from domain.business_relationship.kg_provenance_link_factory import ProvenanceLinkFactory
from domain.business_relationship.kg_provenance_integrity import ProvenanceIntegrityChecker, ProvenanceIntegrityReport
from domain.business_relationship.kg_provenance_result import ProvenanceResult, ProvenanceReport
from domain.business_relationship.kg_identifiers import GraphNodeId
from domain.business_relationship.kg_graph import KnowledgeGraph
from domain.business_relationship.kg_node import GraphNode
from domain.business_relationship.kg_edge import GraphEdge
from domain.business_relationship.canonical_entity import CanonicalEntity
from domain.business_relationship.agreement import Agreement
from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.kg_provenance_source import ProvenanceSource
from domain.business_relationship.kg_provenance_link import ProvenanceLink


class ProvenanceBuilder:
    """Строит новое KnowledgeProvenance из доменных объектов.

    Stateless. Deterministic. NO search. NO traversal. NO navigation.
    NO knowledge creation — only origin description.
    """

    def __init__(self):
        self._source_factory = ProvenanceSourceFactory()
        self._link_factory = ProvenanceLinkFactory()
        self._integrity_checker = ProvenanceIntegrityChecker()

    def build(
        self,
        graph: KnowledgeGraph,
        entity: CanonicalEntity | None = None,
        agreement: Agreement | None = None,
        facts: list[BusinessFact] | None = None,
    ) -> ProvenanceResult:
        """Build KnowledgeProvenance from domain objects."""
        sources: list[tuple[str, ProvenanceSource]] = []
        links: list[ProvenanceLink] = []

        # 1. Entity source
        if entity:
            source = self._source_factory.from_entity(
                entity_id=str(entity.id),
                description=f"Entity {entity.display_name or str(entity.id)}",
            )
            sources.append((str(entity.id), source))
            link = self._link_factory.from_node(
                graph_node_id=GraphNodeId(value=str(entity.id)),
                source=source,
            )
            links.append(link)

        # 2. Agreement source
        if agreement:
            source = self._source_factory.from_agreement(
                agreement_id=str(agreement.id),
                description=f"Agreement {agreement.number or str(agreement.id)}",
            )
            sources.append((str(agreement.id), source))
            link = self._link_factory.from_node(
                graph_node_id=GraphNodeId(value=str(agreement.id)),
                source=source,
            )
            links.append(link)

        # 3. Fact sources
        for fact in (facts or []):
            source = self._source_factory.from_fact(
                fact_id=str(fact.id),
                description=f"Fact {fact.fact_type.value}",
            )
            sources.append((str(fact.id), source))
            link = self._link_factory.from_node(
                graph_node_id=GraphNodeId(value=str(fact.id)),
                source=source,
            )
            links.append(link)

        # 4. Graph nodes sources (all nodes in graph)
        for node in graph.nodes:
            source = self._source_factory.from_entity(
                entity_id=str(node.node_id.value),
                description=f"{node.node_type.value} node {node.node_id.value}",
            )
            sources.append((str(node.node_id.value), source))
            link = self._link_factory.from_node(
                graph_node_id=node.node_id,
                source=source,
            )
            links.append(link)

        # 5. Build chain
        chain = ProvenanceChain(links=tuple(links))

        # 6. Integrity check
        report = self._integrity_checker.check(chain)

        # 7. Build provenance
        provenance = KnowledgeProvenance(
            provenance_id=ProvenanceId.generate(),
            chain=chain,
            metadata=ProvenanceMetadata(
                source_count=len(sources),
                confidence=1.0,
            ),
        )

        return ProvenanceResult(
            provenance=provenance,
            warnings=tuple(report.warnings) + tuple(report.errors) if not report.is_valid else (),
        )
