"""
v2.1.5 — Query Runtime Verification + Explainability Trace.

Diagnostic integration: runs three demo queries after materialization,
traces results back to source document via revision repository.

NO changes to Domain, Query DSL, or Query Engine.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId

from projection.projection_store import ProjectionStore
from projection.projection_query_service import ProjectionQueryService

from query.knowledge_query import KnowledgeQuery
from query.query_target import QueryTarget
from query.return_shape import ReturnShape, ReturnShapeType
from query.explainability import ExplainabilityLevel

from application.knowledge_persistence.knowledge_revision_repository import (
    KnowledgeRevisionRepository,
)

logger = logging.getLogger(__name__)


# ─── Explainability Trace ────────────────────────────────────────────────────

@dataclass(frozen=True)
class QueryTrace:
    """Diagnostic DTO linking a query result back to source document.

    NOT part of Domain. NOT part of Query Engine.
    Application-level diagnostic only.
    """
    query_target: str
    result_summary: str
    result_count: int
    revision_id: str
    explainability_available: bool
    provenance_available: bool
    source_document_id: str
    explanation_confidence: float = 0.0
    provenance_chain_length: int = 0


class QueryExplainabilityResolver:
    """Resolves a KnowledgeRevisionId → KnowledgeRevisionRecord → source document.

    Minimal bridge between query execution and stored revision.
    No Domain business logic. No Query Engine changes.
    """

    def __init__(self, revision_repo: KnowledgeRevisionRepository) -> None:
        self._repo = revision_repo

    def resolve(self, revision_id: str) -> QueryTrace | None:
        """Build a QueryTrace from a revision id string.

        Returns None if revision is not found.
        """
        try:
            rid = KnowledgeRevisionId(value=revision_id)
        except Exception:
            return None
        record = self._repo.get(rid)
        if record is None:
            return None
        rev = record.revision
        snapshot = rev.snapshot
        # Explainability
        exp_available = False
        exp_conf = 0.0
        if snapshot and snapshot.explanation:
            exp_available = True
            exp_conf = snapshot.explanation.overall_confidence or 0.0
        # Provenance
        prov_available = False
        prov_chain_len = 0
        if snapshot and snapshot.provenance:
            prov_available = True
            chain = getattr(snapshot.provenance, "chain", None)
            if chain:
                prov_chain_len = len(getattr(chain, "links", []))
        return QueryTrace(
            query_target="",
            result_summary="",
            result_count=0,
            revision_id=revision_id,
            explainability_available=exp_available,
            provenance_available=prov_available,
            source_document_id=record.source_document_id,
            explanation_confidence=exp_conf,
            provenance_chain_length=prov_chain_len,
        )

    def resolve_with_result(
        self, revision_id: str, query_target: str,
        result_summary: str, result_count: int,
    ) -> QueryTrace:
        trace = self.resolve(revision_id)
        if trace is None:
            return QueryTrace(
                query_target=query_target,
                result_summary=result_summary,
                result_count=result_count,
                revision_id=revision_id,
                explainability_available=False,
                provenance_available=False,
                source_document_id="(revision not found)",
            )
        return QueryTrace(
            query_target=query_target,
            result_summary=result_summary,
            result_count=result_count,
            revision_id=trace.revision_id,
            explainability_available=trace.explainability_available,
            provenance_available=trace.provenance_available,
            source_document_id=trace.source_document_id,
            explanation_confidence=trace.explanation_confidence,
            provenance_chain_length=trace.provenance_chain_length,
        )


# ─── Query Execution ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class QueryResult:
    target: str
    count: int
    summary: str
    success: bool
    error: str = ""


@dataclass(frozen=True)
class QueryBatchResult:
    """All queries + traces for a single document processing cycle."""
    results: tuple[QueryResult, ...] = ()
    traces: tuple[QueryTrace, ...] = ()
    revision_id: str = ""
    source_document_id: str = ""


def run_diagnostic_queries(
    store: ProjectionStore,
    revision_repo: KnowledgeRevisionRepository,
    revision_id: str,
    source_document_id: str,
) -> QueryBatchResult:
    """Run three demo queries and trace results back to source document.

    Non-blocking: errors are captured in result objects, not raised.
    """
    from query_engine.knowledge_query_engine import KnowledgeQueryEngine
    from infrastructure.memory_strategy import InMemoryExecutionStrategy

    qs = ProjectionQueryService(store)
    strategy = InMemoryExecutionStrategy(qs)
    engine = KnowledgeQueryEngine(strategy=strategy)
    resolver = QueryExplainabilityResolver(revision_repo)

    queries = [
        (QueryTarget.ENTITY, "ENTITY"),
        (QueryTarget.AGREEMENT, "AGREEMENT"),
        (QueryTarget.GRAPH, "GRAPH"),
    ]

    query_results: list[QueryResult] = []
    traces: list[QueryTrace] = []

    for qtarget, name in queries:
        try:
            kq = KnowledgeQuery(
                target=qtarget,
                return_shape=ReturnShape(shape_type=ReturnShapeType.SUMMARY),
                explainability=ExplainabilityLevel.SUMMARY,
            )
            result = engine.execute(kq)
            data = getattr(result, "data", result)
            count = 0
            if hasattr(data, "__len__"):
                count = len(data)
            elif isinstance(data, dict):
                count = data.get("count", len(data))
            summary = str(data)[:150]
            qr = QueryResult(target=name, count=count, summary=summary, success=True)
            query_results.append(qr)

            # Trace back to source
            trace = resolver.resolve_with_result(
                revision_id=revision_id,
                query_target=name,
                result_summary=f"{count} items",
                result_count=count,
            )
            traces.append(trace)
        except Exception as e:
            query_results.append(QueryResult(
                target=name, count=0, summary="", success=False, error=str(e)[:200],
            ))

    return QueryBatchResult(
        results=tuple(query_results),
        traces=tuple(traces),
        revision_id=revision_id,
        source_document_id=source_document_id,
    )


# ─── Runtime Logging ─────────────────────────────────────────────────────────

def log_runtime_completed(
    document_id: str,
    revision_id: str,
    revision_number: int,
    projection_count: int,
    query_batch: QueryBatchResult,
    provenance_available: bool,
    explainability_available: bool,
    source_trace_available: bool,
) -> None:
    """Structured runtime log after one document processing cycle."""
    query_counts = {}
    for r in query_batch.results:
        query_counts[r.target] = r.count if r.success else -1

    logger.info(
        "v21_runtime_completed "
        "document_id=%s "
        "revision_id=%s "
        "revision_number=%d "
        "projection_count=%d "
        "query_count=3 "
        "query_result_counts=%s "
        "explanation_available=%s "
        "provenance_available=%s "
        "source_trace_available=%s",
        document_id[:12],
        revision_id[:12],
        revision_number,
        projection_count,
        query_counts,
        "yes" if explainability_available else "no",
        "yes" if provenance_available else "no",
        "yes" if source_trace_available else "no",
    )
