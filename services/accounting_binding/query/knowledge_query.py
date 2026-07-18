"""
KnowledgeQuery — the main immutable query object.

Represents a fully described query intent.
NO execution methods. NO knowledge of Store, Planner, Engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from query.query_target import QueryTarget
from query.predicate import Predicate
from query.predicate_composition import QueryPredicate
from query.return_shape import ReturnShape, ReturnShapeType
from query.explainability import ExplainabilityLevel


@dataclass(frozen=True)
class KnowledgeQuery:
    """Главный immutable объект DSL.

    Полностью описанный запрос.
    Не содержит методов исполнения.
    Не знает ProjectionStore.
    Не знает Planner.
    """
    target: QueryTarget
    predicate: Optional[QueryPredicate] = None
    return_shape: ReturnShape = ReturnShape(shape_type=ReturnShapeType.SUMMARY)
    explainability: ExplainabilityLevel = ExplainabilityLevel.NONE
