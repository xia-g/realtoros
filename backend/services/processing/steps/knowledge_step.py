"""Knowledge Binding Step — creates KnowledgeRevision from pipeline results."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.services.processing.models import PipelineRun, PipelineStep
from backend.services.processing.storage import PipelineRepository
from backend.services.document_lifecycle import DocumentRepository


def execute_knowledge_step(
    pipeline: PipelineRun,
    step: PipelineStep,
    repo: PipelineRepository,
) -> tuple[bool, dict | str]:
    """Execute knowledge binding: create KnowledgeRevision from extracted data.

    Uses existing RevisionBuilder and Repository (no Platform changes).
    """
    from backend.config import settings

    steps = repo.get_steps(pipeline.pipeline_id)

    # Get extraction result
    ext_step = next((s for s in steps if s.step_type == "extraction"), None)
    if not ext_step or not ext_step.result:
        return False, "No extraction result for knowledge binding"

    extraction = ext_step.result
    doc_type = extraction.get("document_type", "unknown")
    fields = extraction.get("fields", {})

    # Get classification for confidence
    class_step = next((s for s in steps if s.step_type == "classification"), None)
    class_confidence = 0.0
    if class_step and class_step.result:
        class_confidence = class_step.result.get("confidence", 0.0)

    # Get OCR quality
    ocr_step = next((s for s in steps if s.step_type == "ocr"), None)
    ocr_confidence = 0.0
    if ocr_step and ocr_step.result:
        ocr_confidence = ocr_step.result.get("ocr", {}).get("confidence", 0.0)

    # Build overall confidence
    overall_confidence = round((ocr_confidence + class_confidence + extraction.get("confidence", 0.0)) / 3, 2)

    # Build KnowledgeGraph from extracted entities
    from domain.business_relationship.kg_graph import KnowledgeGraph
    from domain.business_relationship.kg_node import GraphNode
    from domain.business_relationship.kg_edge import GraphEdge
    from domain.business_relationship.kg_enums import GraphNodeType, GraphEdgeType
    from domain.business_relationship.kg_identifiers import GraphNodeId, GraphEdgeId
    from domain.business_relationship.kg_attributes import GraphAttributes, GraphMetadata as GraphMeta

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    # Document root node
    doc_node_id = GraphNodeId(value="doc-root")
    nodes.append(GraphNode(
        node_id=doc_node_id,
        node_type=GraphNodeType.DOCUMENT,
        domain_id=doc_type,
        attributes=GraphAttributes(label=f"Document: {pipeline.document_id}"),
        metadata=GraphMeta(created_by="pipeline:knowledge-binding"),
    ))

    # Entity nodes from extracted fields
    field_node_ids: dict[str, GraphNodeId] = {}
    for field_name, field_value in fields.items():
        node_id = GraphNodeId(value=f"field-{field_name}")
        field_node_ids[field_name] = node_id
        nodes.append(GraphNode(
            node_id=node_id,
            node_type=GraphNodeType.ENTITY,
            domain_id=field_value[:100],
            attributes=GraphAttributes(label=f"{field_name}: {field_value[:50]}"),
            metadata=GraphMeta(created_by="pipeline:knowledge-binding"),
        ))
        edges.append(GraphEdge(
            edge_id=GraphEdgeId(value=f"edge-doc-{field_name}"),
            edge_type=GraphEdgeType.REFERENCES,
            source_node=doc_node_id,
            target_node=node_id,
        ))

    graph = KnowledgeGraph(nodes=tuple(nodes), edges=tuple(edges))

    # Build KnowledgeSnapshot
    from domain.business_relationship.knowledge_snapshot import KnowledgeSnapshot
    from domain.business_relationship.kg_provenance import KnowledgeProvenance
    from domain.business_relationship.kg_provenance_id import ProvenanceId
    from domain.business_relationship.kg_provenance_chain import ProvenanceChain
    from domain.business_relationship.kg_provenance_link import ProvenanceLink
    from domain.business_relationship.kg_provenance_source import ProvenanceSource, ProvenanceSourceType
    from domain.business_relationship.ke_explanation import GraphExplanation
    from domain.business_relationship.ke_explanation_id import ExplanationId

    provenance = KnowledgeProvenance(
        provenance_id=ProvenanceId.generate(),
        chain=ProvenanceChain(links=(
            ProvenanceLink(
                graph_node_id=doc_node_id,
                source=ProvenanceSource(
                    source_type=ProvenanceSourceType.DOCUMENT,
                    source_id=pipeline.document_id,
                ),
            ),
        )),
    )

    explanation = GraphExplanation(
        explanation_id=ExplanationId.generate(),
        graph_node_id=doc_node_id,
    )

    snapshot = KnowledgeSnapshot(
        graph=graph,
        provenance=provenance,
        explanation=explanation,
    )

    # Build KnowledgeRevision
    from domain.business_relationship.knowledge_revision import KnowledgeRevision
    from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId
    from domain.business_relationship.knowledge_revision_number import KnowledgeRevisionNumber
    from domain.business_relationship.knowledge_revision_metadata import KnowledgeRevisionMetadata

    rev_id = f"pipeline-{pipeline.pipeline_id[:8]}"
    rev_number = 1  # first revision from pipeline

    # Check if there's an existing revision for this document
    # Use in-memory repo (PostgreSQL not implemented for Knowledge Layer)
    from infrastructure.knowledge_persistence.memory_knowledge_revision_repository import MemoryKnowledgeRevisionRepository
    revision_repo = MemoryKnowledgeRevisionRepository()
    existing_records = revision_repo.get_by_document_id(pipeline.document_id)
    if existing_records:
        max_num = max(r.revision.revision_number.number for r in existing_records)
        rev_number = max_num + 1

    revision = KnowledgeRevision(
        revision_id=KnowledgeRevisionId(value=rev_id),
        revision_number=KnowledgeRevisionNumber(number=rev_number),
        snapshot=snapshot,
        metadata=KnowledgeRevisionMetadata(
            created_at=datetime.now(timezone.utc),
            created_by="pipeline:document-processing",
            reason=f"Pipeline processing: {doc_type} confidence={overall_confidence}",
            document_count=1,
        ),
    )

    # Save via existing repository
    from application.knowledge_persistence.knowledge_revision_record import KnowledgeRevisionRecord
    record = KnowledgeRevisionRecord(
        revision=revision,
        explanation=revision.snapshot.explanation,
        source_document_id=pipeline.document_id,
    )
    revision_repo.save(record)

    # Update document profile
    doc_repo = DocumentRepository(dsn=settings.DATABASE_SYNC_URL)
    doc = doc_repo.get(pipeline.document_id)
    if doc:
        doc.profile.update({
            "confidence": overall_confidence,
            "document_type": doc_type,
            "knowledge_revision_id": rev_id,
        })
        doc_repo.save(doc)

    return True, {
        "knowledge_revision_id": rev_id,
        "revision_number": rev_number,
        "confidence": overall_confidence,
        "document_type": doc_type,
        "fields_count": len(fields),
        "graph_nodes": len(nodes),
        "graph_edges": len(edges),
    }
