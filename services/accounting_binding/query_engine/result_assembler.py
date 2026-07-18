"""
ResultAssembler — builds QueryResult from projections.

Considers ReturnShape, Explainability, Field Selection.
Does NOT execute queries.
"""
from __future__ import annotations

from typing import Optional

from projection.projection import Projection
from query.knowledge_query import KnowledgeQuery
from query.return_shape import ReturnShape, ReturnShapeType
from query.explainability import ExplainabilityLevel
from query_engine.execution_plan import ExecutionPlan
from query_engine.query_result import QueryResult, QueryMetadata


class ResultAssembler:
    """Собирает QueryResult из полученных Projection.

    Учитывает ReturnShape, Explainability, Field Selection.
    Не выполняет Query.
    """

    @staticmethod
    def assemble(
        query: KnowledgeQuery,
        projections: tuple[Projection, ...],
        execution_time_ms: float = 0.0,
    ) -> QueryResult:
        """Assemble QueryResult from resolved projections."""
        # Apply return shape
        shape = query.return_shape
        if shape.shape_type == ReturnShapeType.IDENTIFIERS_ONLY:
            # Keep projections but mark as identifiers-only
            pass
        elif shape.shape_type == ReturnShapeType.FIELDS:
            # In real strategy, fields would be selected here
            pass
        # FULL_PROJECTION and SUMMARY pass through

        # Collect explainability if requested
        explanations: tuple[str, ...] = ()
        if query.explainability != ExplainabilityLevel.NONE:
            expl_list: list[str] = []
            for proj in projections:
                if query.explainability == ExplainabilityLevel.FULL:
                    expl_list.append(
                        f"Projection {proj.projection_id.value}: "
                        f"type={proj.projection_type.name}"
                    )
                elif query.explainability == ExplainabilityLevel.SUMMARY:
                    expl_list.append(
                        f"Found {proj.projection_type.name} "
                        f"({proj.projection_id.value})"
                    )
            explanations = tuple(expl_list)

        # Build resolve order from projection types
        resolve_order = tuple(
            p.projection_type.name for p in projections
        )

        metadata = QueryMetadata(
            total_found=len(projections),
            execution_time_ms=execution_time_ms,
            resolve_order=resolve_order,
        )

        return QueryResult(
            query=query,
            projections=projections,
            explainability=explanations,
            metadata=metadata,
        )
