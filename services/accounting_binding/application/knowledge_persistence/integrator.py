"""
KnowledgeRuntimeIntegrator — application-level orchestrator for v2.1.5.

Holds shared MemoryKnowledgeRevisionRepository and MemoryProjectionStore
at application lifetime. Single `integrate()` call does:

    pipeline_result → KnowledgeRevisionRecord → save → materialize → query → report

NO changes to Domain, Projection Layer, Query DSL, or Query Engine.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from domain.business_relationship.knowledge_revision import KnowledgeRevision
from domain.business_relationship.ke_explanation import GraphExplanation
from domain.business_relationship.ke_explanation_id import ExplanationId

from projection.projection import ProjectionType
from projection.projection_registry import ProjectionRegistry
from projection.build_plan import BuildPlan, BuildStep
from projection.projection_store import ProjectionStore

from infrastructure.memory_store import MemoryProjectionStore
from infrastructure.knowledge_persistence import MemoryKnowledgeRevisionRepository

from application.knowledge_persistence.knowledge_revision_record import KnowledgeRevisionRecord
from application.knowledge_persistence.knowledge_revision_repository import (
    KnowledgeRevisionRepository,
    KnowledgeRevisionConflictError,
)
from application.knowledge_persistence.materialization import (
    materialize as _materialize,
    MaterializationResult,
    MaterializedEntityBuilder,
    MaterializedAgreementBuilder,
    MaterializedGraphBuilder,
    MaterializedProvenanceBuilder,
)
from application.knowledge_persistence.query_verification import (
    run_diagnostic_queries,
    QueryBatchResult,
)

logger = logging.getLogger(__name__)


# ─── Runtime Report DTO ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class KnowledgeRuntimeReport:
    """Immutable DTO summarising one document processing cycle.

    NOT part of Domain. NOT part of any HTTP response contract.
    Used for internal diagnostics and structured logging only.
    """
    revision_id: str = ""
    revision_number: int = 0
    source_document_id: str = ""
    projection_count: int = 0
    projection_types: tuple[str, ...] = ()
    query_result_counts: dict[str, int] = field(default_factory=dict)
    explanation_available: bool = False
    provenance_available: bool = False
    source_trace_available: bool = False
    status: str = "unknown"
    error_count: int = 0
    persisted: bool = False


# ─── Integrator ─────────────────────────────────────────────────────────────

class KnowledgeRuntimeIntegrator:
    """Application-level orchestrator for knowledge runtime.

    Receives already-created dependencies via DI.
    Knows only KnowledgeRevisionRepository and ProjectionStore protocols.
    No knowledge of PostgreSQL, Memory, or any concrete implementation.

    Shared instances:
      - revision_repository: KnowledgeRevisionRepository
      - projection_store: ProjectionStore
      - projection_registry: ProjectionRegistry
      - build_plan: BuildPlan

    Single-threaded. Not thread-safe.
    """

    def __init__(
        self,
        revision_repository=None,
        projection_store=None,
    ) -> None:
        self.revision_repository = revision_repository or MemoryKnowledgeRevisionRepository()
        self.projection_store = projection_store or MemoryProjectionStore()

        self._registry = ProjectionRegistry()
        self._registry.register(MaterializedEntityBuilder())
        self._registry.register(MaterializedAgreementBuilder())
        self._registry.register(MaterializedGraphBuilder())
        self._registry.register(MaterializedProvenanceBuilder())

        self._plan = BuildPlan.custom(steps=(
            BuildStep(projection_type=ProjectionType.ENTITY, depends_on=()),
            BuildStep(projection_type=ProjectionType.AGREEMENT, depends_on=(ProjectionType.ENTITY,)),
            BuildStep(projection_type=ProjectionType.GRAPH, depends_on=(ProjectionType.ENTITY, ProjectionType.AGREEMENT)),
            BuildStep(projection_type=ProjectionType.PROVENANCE, depends_on=(ProjectionType.GRAPH,)),
        ))

    def integrate(
        self,
        *,
        pipeline_result: dict,
        source_document_id: str,
        processing_job_id: str | None = None,
    ) -> KnowledgeRuntimeReport:
        logger.info("knowledge_runtime_started document_id=%s", source_document_id[:12])
        errors: list[str] = []

        # ── Step 1: Extract revision + explanation from pipeline result ──
        try:
            raw_revision = pipeline_result.get("revision")
            if raw_revision is None:
                raise ValueError("pipeline_result must contain 'revision'")

            # Handle both KnowledgeRevision objects and dicts from real pipeline
            if isinstance(raw_revision, KnowledgeRevision):
                revision = raw_revision
                revision_id = revision.revision_id.value
                revision_number = revision.revision_number.number
                raw_explanation = pipeline_result.get("explanation")
                if raw_explanation is None and revision.snapshot and revision.snapshot.explanation:
                    raw_explanation = revision.snapshot.explanation
            elif isinstance(raw_revision, dict):
                # Dict path — from real DomainPipelineBridge.process()
                revision_id = raw_revision.get("id", "")
                revision_number = raw_revision.get("number", 0)
                # Build a minimal KnowledgeRevision for the record
                from domain.business_relationship.knowledge_revision import KnowledgeRevision as KR
                from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId as KRID
                from domain.business_relationship.knowledge_revision_number import KnowledgeRevisionNumber as KRN
                revision = KR(
                    revision_id=KRID(value=revision_id),
                    revision_number=KRN(number=revision_number),
                    snapshot=raw_revision.get("snapshot"),
                    metadata={},
                )
                raw_explanation = None
                if revision.snapshot and revision.snapshot.explanation:
                    raw_explanation = revision.snapshot.explanation
            else:
                raise ValueError(f"unexpected revision type: {type(raw_revision).__name__}")

            if raw_explanation is None:
                raw_explanation = GraphExplanation(
                    explanation_id=ExplanationId(value=revision_id or "unknown"),
                    graph_node_id="", steps=(),
                    overall_confidence=0.0, metadata={},
                )
        except Exception as e:
            logger.error("knowledge_runtime revision extraction failed: %s", e)
            return KnowledgeRuntimeReport(
                source_document_id=source_document_id,
                status="revision_extraction_failed",
                error_count=1,
            )

        # ── Step 2: Save record ──
        try:
            record = KnowledgeRevisionRecord(
                revision=revision,
                explanation=raw_explanation,
                source_document_id=source_document_id,
                processing_job_id=processing_job_id,
            )
            self.revision_repository.save(record)
            persisted = True
            logger.info(
                "knowledge_revision_persisted revision_id=%s source_doc=%s",
                revision_id[:12], source_document_id[:12],
            )
        except KnowledgeRevisionConflictError:
            logger.warning(
                "knowledge_revision_conflict revision_id=%s — idempotent re-save skipped",
                revision_id[:12],
            )
            persisted = True
        except Exception as e:
            logger.error("knowledge_revision_persist_failed revision_id=%s: %s", revision_id[:12], e)
            return KnowledgeRuntimeReport(
                source_document_id=source_document_id,
                revision_id=revision_id,
                revision_number=revision_number,
                status="persistence_failed",
                error_count=1,
            )

        # ── Step 3: Materialize projections ──
        projection_count = 0
        projection_types: list[str] = []
        try:
            mat_result = _materialize(
                revision, self._registry, self.projection_store, self._plan,
            )
            if mat_result.errors:
                errors.extend(f"materialize_{e}" for e in mat_result.errors)
                logger.warning(
                    "projection_materialization_errors revision_id=%s errors=%s",
                    revision_id[:12], list(mat_result.errors),
                )
            projection_count = len(mat_result.built)
            projection_types = [p.projection_type.name for p in mat_result.built]
            logger.info(
                "projection_materialization_completed revision_id=%s count=%d types=%s",
                revision_id[:12], projection_count, projection_types,
            )
        except Exception as e:
            errors.append(f"materialization: {e}")
            logger.error(
                "projection_materialization_failed revision_id=%s: %s",
                revision_id[:12], e,
            )
            # Revision stays saved — proceed to report

        # ── Step 4: Diagnostic queries ──
        query_counts: dict[str, int] = {}
        query_batch: QueryBatchResult | None = None
        try:
            query_batch = run_diagnostic_queries(
                store=self.projection_store,
                revision_repo=self.revision_repository,
                revision_id=revision_id,
                source_document_id=source_document_id,
            )
            for r in query_batch.results:
                key = r.target.lower()
                query_counts[key] = r.count if r.success else -1
                if not r.success:
                    logger.warning(
                        "diagnostic_query_failed revision_id=%s target=%s error=%s",
                        revision_id[:12], r.target, r.error,
                    )
            logger.info(
                "knowledge_query_verification_completed revision_id=%s results=%s",
                revision_id[:12], query_counts,
            )
        except Exception as e:
            logger.warning(
                "knowledge_query_verification_failed revision_id=%s: %s",
                revision_id[:12], e,
            )

        # ── Step 5: Check provenance & explanation ──
        explanation_available = False
        provenance_available = False
        try:
            if revision.snapshot:
                if revision.snapshot.explanation is not None:
                    explanation_available = True
                if revision.snapshot.provenance is not None:
                    provenance_available = True
        except Exception:
            pass

        source_trace_available = False
        if query_batch:
            try:
                for t in query_batch.traces:
                    if t.source_document_id and t.source_document_id != "(revision not found)":
                        source_trace_available = True
                        break
            except Exception:
                pass

        report = KnowledgeRuntimeReport(
            revision_id=revision_id,
            revision_number=revision_number,
            source_document_id=source_document_id,
            projection_count=projection_count,
            projection_types=tuple(projection_types),
            query_result_counts=query_counts,
            explanation_available=explanation_available,
            provenance_available=provenance_available,
            source_trace_available=source_trace_available,
            status="completed" if not errors else "partial",
            error_count=len(errors),
            persisted=persisted,
        )

        logger.info(
            "knowledge_runtime_completed "
            "document_id=%s revision_id=%s rev_num=%d "
            "projections=%d types=%s "
            "entity=%d agreement=%d graph=%d "
            "explanation=%s provenance=%s source_trace=%s",
            source_document_id[:12], revision_id[:12], revision_number,
            projection_count, projection_types,
            query_counts.get("entity", 0),
            query_counts.get("agreement", 0),
            query_counts.get("graph", 0),
            "yes" if explanation_available else "no",
            "yes" if provenance_available else "no",
            "yes" if source_trace_available else "no",
        )
        return report
