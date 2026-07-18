"""
v2.1.5 — Runtime Pipeline Integration.

Wires the full cycle: DomainPipelineBridge → KnowledgeRevisionRecord → 
MemoryKnowledgeRevisionRepository → materialize() → QUERY → Explainability.

Single entry point: run_v21_5_pipeline() — called from uploads.py.
"""
from __future__ import annotations

import logging

from infrastructure.memory_store import MemoryProjectionStore
from infrastructure.knowledge_persistence import MemoryKnowledgeRevisionRepository

from projection.projection_registry import ProjectionRegistry
from projection.build_plan import BuildPlan, BuildStep
from projection.projection import ProjectionType

from application.knowledge_persistence.knowledge_revision_record import KnowledgeRevisionRecord
from application.knowledge_persistence.materialization import (
    materialize,
    MaterializedEntityBuilder,
    MaterializedAgreementBuilder,
    MaterializedGraphBuilder,
    MaterializedProvenanceBuilder,
)
from application.knowledge_persistence.query_verification import (
    run_diagnostic_queries,
    log_runtime_completed,
)

logger = logging.getLogger(__name__)


def build_pipeline_components():
    """Create fresh instances of pipeline components.

    Each call returns independent components so multiple document
    processing cycles do not share state.
    """
    registry = ProjectionRegistry()
    registry.register(MaterializedEntityBuilder())
    registry.register(MaterializedAgreementBuilder())
    registry.register(MaterializedGraphBuilder())
    registry.register(MaterializedProvenanceBuilder())

    plan = BuildPlan.custom(steps=(
        BuildStep(projection_type=ProjectionType.ENTITY, depends_on=()),
        BuildStep(projection_type=ProjectionType.AGREEMENT, depends_on=(ProjectionType.ENTITY,)),
        BuildStep(projection_type=ProjectionType.GRAPH, depends_on=(ProjectionType.ENTITY, ProjectionType.AGREEMENT)),
        BuildStep(projection_type=ProjectionType.PROVENANCE, depends_on=(ProjectionType.GRAPH,)),
    ))

    store = MemoryProjectionStore()
    revision_repo = MemoryKnowledgeRevisionRepository()

    return registry, plan, store, revision_repo


def run_v21_5_pipeline(
    pipeline_result: dict,
    registry: ProjectionRegistry,
    plan: BuildPlan,
    store: MemoryProjectionStore,
    revision_repo: MemoryKnowledgeRevisionRepository,
) -> dict:
    """Execute the full v2.1.5 runtime integration for one document.

    Called after DomainPipelineBridge.process() returns.

    Returns diagnostic summary dict. Does NOT raise on query/materialization errors.
    """
    stages: dict = {"status": "ok", "errors": []}

    # ── 1. Build KnowledgeRevisionRecord ──
    try:
        revision = pipeline_result.get("revision", {})
        # Get explanation from pipeline_result or from revision snapshot
        explanation = pipeline_result.get("explanation", None)
        if explanation is None and isinstance(revision, dict):
            snap = revision.get("snapshot")
            if snap and hasattr(snap, "explanation") and snap.explanation:
                explanation = snap.explanation

        source_doc_id = pipeline_result.get("document_id", "")
        revision_id = ""
        if isinstance(revision, dict):
            revision_id = revision.get("id", "")
            revision_number = revision.get("number", 0)
        else:
            rid_obj = getattr(revision, "revision_id", "")
            revision_id = getattr(rid_obj, "value", str(rid_obj))
            revision_number = getattr(getattr(revision, "revision_number", None), "number", 0)

        stages["revision_id"] = revision_id
        stages["revision_number"] = revision_number
        stages["source_document_id"] = source_doc_id
    except Exception as e:
        stages["errors"].append(f"revision_record: {e}")
        stages["status"] = "revision_failed"
        return stages

    # ── 2. Save to repository ──
    provenance_available = False
    explainability_available = False
    try:
        from domain.business_relationship.ke_explanation import GraphExplanation
        from domain.business_relationship.ke_explanation_id import ExplanationId
        # Create a minimal explanation if missing
        if explanation is None:
            explanation = GraphExplanation(
                explanation_id=ExplanationId(value=revision_id or "unknown"),
                graph_node_id="",
                steps=(),
                overall_confidence=0.0,
                metadata={},
            )

        record = KnowledgeRevisionRecord(
            revision=revision,
            explanation=explanation,
            source_document_id=source_doc_id,
            processing_job_id=pipeline_result.get("document_id", ""),
        )
        revision_repo.save(record)

        # Check provenance and explanation on revision snapshot
        rev_snapshot = getattr(revision, "snapshot", None) if not isinstance(revision, dict) else revision.get("snapshot")
        if rev_snapshot:
            if hasattr(rev_snapshot, "provenance") and rev_snapshot.provenance:
                provenance_available = True
            if hasattr(rev_snapshot, "explanation") and rev_snapshot.explanation:
                explainability_available = True

        logger.info("knowledge_revision_persisted revision_id=%s source_doc_id=%s", revision_id[:12], source_doc_id[:12])
    except Exception as e:
        stages["errors"].append(f"persistence: {e}")
        stages["status"] = "persistence_failed"
        return stages

    # ── 3. Materialize projections ──
    projection_count = 0
    projection_types = []
    try:
        mat_result = materialize(revision, registry, store, plan)
        if mat_result.errors:
            stages["materialization_errors"] = list(mat_result.errors)
        projection_count = len(mat_result.built)
        projection_types = [p.projection_type.name for p in mat_result.built]
        logger.info(
            "projection_materialization_completed revision_id=%s projections=%d types=%s",
            revision_id[:12], projection_count, projection_types,
        )
    except Exception as e:
        logger.warning("projection_materialization_failed revision_id=%s error=%s", revision_id[:12], e)
        stages["errors"].append(f"materialization: {e}")
        stages["status"] = "materialization_failed"
        # Revision stays saved — do NOT return

    # ── 4. Run diagnostic queries ──
    query_batch = None
    try:
        query_batch = run_diagnostic_queries(
            store=store,
            revision_repo=revision_repo,
            revision_id=revision_id,
            source_document_id=source_doc_id,
        )
        for r in query_batch.results:
            if not r.success:
                logger.warning("diagnostic_query_failed target=%s error=%s", r.target, r.error)

        stages["queries"] = {
            r.target: {"count": r.count, "success": r.success}
            for r in query_batch.results
        }
    except Exception as e:
        logger.warning("diagnostic_queries_failed: %s", e)
        stages["query_error"] = str(e)[:200]

    # ── 5. Structured logging ──
    source_trace_available = bool(
        query_batch and any(
            t.source_document_id and t.source_document_id != "(revision not found)"
            for t in query_batch.traces
        )
    ) if query_batch else False

    try:
        log_runtime_completed(
            document_id=source_doc_id,
            revision_id=revision_id,
            revision_number=stages.get("revision_number", 0) if not isinstance(stages.get("revision_number", 0), str) else 0,
            projection_count=projection_count,
            query_batch=query_batch or type("Empty", (), {"results": (), "traces": ()})(),
            provenance_available=provenance_available,
            explainability_available=explainability_available,
            source_trace_available=source_trace_available,
        )
    except Exception as e:
        logger.warning("runtime_logging_failed: %s", e)

    stages["provenance_available"] = provenance_available
    stages["explainability_available"] = explainability_available
    stages["source_trace_available"] = source_trace_available
    stages["projection_count"] = projection_count
    stages["projection_types"] = projection_types

    return stages
