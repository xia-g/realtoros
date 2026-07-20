"""
v2.3 — PostgreSQL serialisation codec for KnowledgeRevision objects.

Converts between Domain objects (KnowledgeRevision, KnowledgeSnapshot,
KnowledgeGraph, KnowledgeProvenance, GraphExplanation) and 
JSON-serialisable dicts for PostgreSQL JSONB columns.

NOT part of Domain. Infrastructure only.
"""
from __future__ import annotations

from dataclasses import is_dataclass, fields as dc_fields
from datetime import datetime
from typing import Any

from domain.business_relationship.knowledge_revision import KnowledgeRevision
from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId
from domain.business_relationship.knowledge_revision_number import KnowledgeRevisionNumber
from domain.business_relationship.knowledge_revision_metadata import KnowledgeRevisionMetadata
from domain.business_relationship.knowledge_snapshot import KnowledgeSnapshot
from domain.business_relationship.kg_graph import KnowledgeGraph
from domain.business_relationship.kg_node import GraphNode
from domain.business_relationship.kg_edge import GraphEdge
from domain.business_relationship.kg_enums import GraphNodeType, GraphEdgeType
from domain.business_relationship.kg_identifiers import GraphNodeId, GraphEdgeId
from domain.business_relationship.kg_attributes import GraphAttributes, GraphMetadata
from domain.business_relationship.kg_provenance import KnowledgeProvenance
from domain.business_relationship.kg_provenance_id import ProvenanceId
from domain.business_relationship.kg_provenance_chain import ProvenanceChain
from domain.business_relationship.kg_provenance_link import ProvenanceLink
from domain.business_relationship.kg_provenance_source import ProvenanceSource, ProvenanceSourceType
from domain.business_relationship.kg_provenance_metadata import ProvenanceMetadata
from domain.business_relationship.ke_explanation import GraphExplanation
from domain.business_relationship.ke_explanation_id import ExplanationId
from domain.business_relationship.ke_explanation_step import ExplanationStep
from domain.business_relationship.ke_explanation_reason import ExplanationReasonType
from domain.business_relationship.ke_explanation_parts import ExplanationReason, ExplanationEvidence
from domain.business_relationship.ke_explanation_metadata import ExplanationMetadata
from domain.business_relationship.kg_identifiers import GraphNodeId


# ── Helpers ──────────────────────────────────────────────────────

def _dt_to_str(dt: datetime | None) -> str | None:
    if dt is None or dt == datetime.min:
        return None
    return dt.isoformat()


def _str_to_dt(s: str | None) -> datetime:
    if not s:
        return datetime.min
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return datetime.min


def _enum_val(e) -> str:
    return e.value if hasattr(e, 'value') else str(e)


def _str_to_enum(cls, s: str | None, default=None):
    if s is None:
        return default
    try:
        return cls(s)
    except (ValueError, TypeError):
        return default


# ── GraphMetadata serialisation ──────────────────────────────────

def _ser_gm(meta: GraphMetadata | None) -> dict | None:
    if meta is None:
        return None
    return {
        "created_at": _dt_to_str(meta.created_at),
        "created_by": meta.created_by,
        "knowledge_revision_hint": meta.knowledge_revision_hint,
        "schema_version": meta.schema_version,
    }


def _deser_gm(data: dict | None) -> GraphMetadata:
    if data is None:
        return GraphMetadata()
    return GraphMetadata(
        created_at=_str_to_dt(data.get("created_at")),
        created_by=data.get("created_by", ""),
        knowledge_revision_hint=data.get("knowledge_revision_hint", 0),
        schema_version=data.get("schema_version", 1),
    )


# ── GraphAttributes serialisation ────────────────────────────────

def _ser_ga(attr: GraphAttributes | None) -> dict | None:
    if attr is None:
        return None
    return {
        "label": attr.label,
        "display_name": attr.display_name,
        "tags": list(attr.tags),
        "properties": [[k, v] for k, v in attr.properties],
    }


def _deser_ga(data: dict | None) -> GraphAttributes:
    if data is None:
        return GraphAttributes()
    return GraphAttributes(
        label=data.get("label", ""),
        display_name=data.get("display_name", ""),
        tags=tuple(data.get("tags", [])),
        properties=tuple((k, v) for k, v in data.get("properties", [])),
    )


# ── Graph serialisation ──────────────────────────────────────────

def _ser_graph(graph: KnowledgeGraph) -> dict:
    nodes = []
    for n in graph.nodes:
        nodes.append({
            "node_id": n.node_id.value,
            "node_type": _enum_val(n.node_type),
            "domain_id": n.domain_id,
            "attributes": _ser_ga(n.attributes),
            "metadata": _ser_gm(n.metadata),
        })
    edges = []
    for e in graph.edges:
        edges.append({
            "edge_id": e.edge_id.value,
            "edge_type": _enum_val(e.edge_type),
            "source_node": e.source_node.value,
            "target_node": e.target_node.value,
            "attributes": _ser_ga(e.attributes),
            "metadata": _ser_gm(e.metadata),
        })
    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": _ser_gm(graph.metadata),
    }


def _deser_graph(data: dict | None) -> KnowledgeGraph:
    if data is None:
        return KnowledgeGraph()
    nodes = []
    for nd in data.get("nodes", []):
        nodes.append(GraphNode(
            node_id=GraphNodeId(value=nd["node_id"]),
            node_type=_str_to_enum(GraphNodeType, nd.get("node_type"), GraphNodeType.ENTITY),
            domain_id=nd.get("domain_id", ""),
            attributes=_deser_ga(nd.get("attributes")),
            metadata=_deser_gm(nd.get("metadata")),
        ))
    edges = []
    for ed in data.get("edges", []):
        edges.append(GraphEdge(
            edge_id=GraphEdgeId(value=ed.get("edge_id", "")),
            edge_type=_str_to_enum(GraphEdgeType, ed.get("edge_type"), GraphEdgeType.REFERENCES),
            source_node=GraphNodeId(value=ed["source_node"]),
            target_node=GraphNodeId(value=ed["target_node"]),
            attributes=_deser_ga(ed.get("attributes")),
            metadata=_deser_gm(ed.get("metadata")),
        ))
    return KnowledgeGraph(
        nodes=tuple(nodes),
        edges=tuple(edges),
        metadata=_deser_gm(data.get("metadata")),
    )


# ── Provenance serialisation ─────────────────────────────────────

def _ser_provenance(provenance: KnowledgeProvenance | None) -> dict | None:
    if provenance is None:
        return None
    links = []
    for link in provenance.chain.links:
        links.append({
            "graph_node_id": link.graph_node_id.value,
            "source": {
                "source_type": _enum_val(link.source.source_type),
                "source_id": link.source.source_id,
                "description": link.source.description,
            },
            "confidence": link.confidence,
        })
    meta = provenance.metadata
    return {
        "provenance_id": provenance.provenance_id.value,
        "links": links,
        "metadata": {
            "created_at": _dt_to_str(meta.created_at) if meta else None,
            "source_count": meta.source_count if meta else 0,
            "confidence": meta.confidence if meta else 1.0,
            "revision_hint": meta.revision_hint if meta else 0,
        },
    }


def _deser_provenance(data: dict | None) -> KnowledgeProvenance:
    if data is None:
        return KnowledgeProvenance(provenance_id=ProvenanceId.generate())
    link_objs = []
    for ld in data.get("links", []):
        src = ld.get("source", {})
        source = ProvenanceSource(
            source_type=_str_to_enum(ProvenanceSourceType, src.get("source_type"), ProvenanceSourceType.DOCUMENT),
            source_id=src.get("source_id", ""),
            description=src.get("description", ""),
        )
        link_objs.append(ProvenanceLink(
            graph_node_id=GraphNodeId(value=ld.get("graph_node_id", "")),
            source=source,
            confidence=ld.get("confidence", 1.0),
        ))
    meta_md = data.get("metadata", {})
    metadata = ProvenanceMetadata(
        created_at=_str_to_dt(meta_md.get("created_at")),
        source_count=meta_md.get("source_count", len(link_objs)),
        confidence=meta_md.get("confidence", 1.0),
        revision_hint=meta_md.get("revision_hint", 0),
    )
    return KnowledgeProvenance(
        provenance_id=ProvenanceId.from_string(data.get("provenance_id", "")),
        chain=ProvenanceChain(links=tuple(link_objs)),
        metadata=metadata,
    )


# ── Explanation serialisation ────────────────────────────────────

def _ser_explanation(explanation: GraphExplanation | None) -> dict | None:
    if explanation is None:
        return None
    steps = []
    for step in explanation.steps:
        reasons = [
            {
                "reason_type": _enum_val(r.reason_type),
                "summary": r.summary,
                "confidence": r.confidence,
                "related_domain_id": r.related_domain_id,
            }
            for r in step.reasons
        ]
        evidence = [
            {
                "source_type": ev.source_type,
                "source_id": ev.source_id,
                "description": ev.description,
                "confidence": ev.confidence,
            }
            for ev in step.evidence
        ]
        steps.append({
            "step_number": step.step_number,
            "summary": step.summary,
            "reasons": reasons,
            "evidence": evidence,
        })
    meta = explanation.metadata
    return {
        "explanation_id": explanation.explanation_id.value,
        "graph_node_id": explanation.graph_node_id.value,
        "steps": steps,
        "overall_confidence": explanation.overall_confidence,
        "metadata": {
            "created_at": _dt_to_str(meta.created_at) if meta else None,
            "created_by": meta.created_by if meta else "",
            "knowledge_revision_hint": meta.knowledge_revision_hint if meta else 0,
            "schema_version": meta.schema_version if meta else 1,
        },
    }


def _deser_explanation(data: dict | None) -> GraphExplanation:
    if data is None:
        return GraphExplanation(
            explanation_id=ExplanationId.generate(),
            graph_node_id=GraphNodeId(value="root"),
        )
    step_objs = []
    for sd in data.get("steps", []):
        reasons = [
            ExplanationReason(
                reason_type=_str_to_enum(ExplanationReasonType, rd.get("reason_type"), ExplanationReasonType.DERIVED),
                summary=rd.get("summary", ""),
                confidence=rd.get("confidence", 1.0),
                related_domain_id=rd.get("related_domain_id", ""),
            )
            for rd in sd.get("reasons", [])
        ]
        evidence = [
            ExplanationEvidence(
                source_type=evd.get("source_type", ""),
                source_id=evd.get("source_id", ""),
                description=evd.get("description", ""),
                confidence=evd.get("confidence", 1.0),
            )
            for evd in sd.get("evidence", [])
        ]
        step_objs.append(ExplanationStep(
            step_number=sd.get("step_number", 0),
            summary=sd.get("summary", ""),
            reasons=tuple(reasons),
            evidence=tuple(evidence),
        ))
    meta = data.get("metadata", {})
    metadata = ExplanationMetadata(
        created_at=_str_to_dt(meta.get("created_at")),
        created_by=meta.get("created_by", ""),
        knowledge_revision_hint=meta.get("knowledge_revision_hint", 0),
        schema_version=meta.get("schema_version", 1),
    )
    return GraphExplanation(
        explanation_id=ExplanationId.from_string(data.get("explanation_id", "")),
        graph_node_id=GraphNodeId(value=data.get("graph_node_id", "root")),
        steps=tuple(step_objs),
        overall_confidence=data.get("overall_confidence", 1.0),
        metadata=metadata,
    )


# ── Snapshot serialisation ───────────────────────────────────────

def serialise_snapshot(snapshot: KnowledgeSnapshot | None) -> dict | None:
    if snapshot is None:
        return None
    return {
        "graph": _ser_graph(snapshot.graph),
        "provenance": _ser_provenance(snapshot.provenance),
        "explanation": _ser_explanation(snapshot.explanation),
    }


def deserialise_snapshot(data: dict | None) -> KnowledgeSnapshot:
    if data is None:
        return KnowledgeSnapshot.empty()
    return KnowledgeSnapshot(
        graph=_deser_graph(data.get("graph")),
        provenance=_deser_provenance(data.get("provenance")),
        explanation=_deser_explanation(data.get("explanation")),
    )


# ── Metadata serialisation ───────────────────────────────────────

def serialise_metadata(meta: KnowledgeRevisionMetadata) -> dict:
    return {
        "created_at": _dt_to_str(meta.created_at),
        "created_by": meta.created_by,
        "reason": meta.reason,
        "document_count": meta.document_count,
        "entity_count": meta.entity_count,
        "graph_digest_hint": meta.graph_digest_hint,
    }


def deserialise_metadata(data: dict | None) -> KnowledgeRevisionMetadata:
    if data is None:
        return KnowledgeRevisionMetadata()
    return KnowledgeRevisionMetadata(
        created_at=_str_to_dt(data.get("created_at")),
        created_by=data.get("created_by", ""),
        reason=data.get("reason", ""),
        document_count=data.get("document_count", 0),
        entity_count=data.get("entity_count", 0),
        graph_digest_hint=data.get("graph_digest_hint", ""),
    )
