"""
ExecutionPlan — immutable description of query execution.

Contains: target projection, predicate tree, required properties,
return shape, explainability level, resolution steps.
NO execution code.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Union

from query.knowledge_query import KnowledgeQuery
from query.query_target import QueryTarget
from query.predicate import Predicate
from query.predicate_composition import QueryPredicate, And, Or, Not
from query.return_shape import ReturnShape, ReturnShapeType
from query.explainability import ExplainabilityLevel


@dataclass(frozen=True)
class ResolutionStep:
    """Один шаг исполнения: резолв одной проекции."""
    target: QueryTarget
    depends_on: tuple[QueryTarget, ...] = ()


@dataclass(frozen=True)
class ExecutionPlan:
    """Immutable описание процесса исполнения.

    Содержит всё необходимое для исполнения.
    Не содержит кода исполнения.
    """
    target: QueryTarget
    predicate: Optional[QueryPredicate] = None
    return_shape: ReturnShape = ReturnShape(shape_type=ReturnShapeType.SUMMARY)
    explainability: ExplainabilityLevel = ExplainabilityLevel.NONE
    resolution_steps: tuple[ResolutionStep, ...] = ()

    @classmethod
    def from_query(cls, query: KnowledgeQuery) -> ExecutionPlan:
        """Create an execution plan from a KnowledgeQuery."""
        return cls(
            target=query.target,
            predicate=query.predicate,
            return_shape=query.return_shape,
            explainability=query.explainability,
        )
