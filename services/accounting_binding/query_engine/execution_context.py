"""
ExecutionContext — immutable context for query execution.

Contains: ExecutionPlan, Strategy, Explainability Mode.
No mutable state.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from query_engine.execution_plan import ExecutionPlan
from query_engine.execution_strategy import ExecutionStrategy
from query.explainability import ExplainabilityLevel


@dataclass(frozen=True)
class ExecutionContext:
    """Immutable контекст исполнения.

    Содержит план, стратегию и режим Explainability.
    Не содержит mutable состояния.
    """
    plan: ExecutionPlan
    strategy: ExecutionStrategy
    explainability: ExplainabilityLevel = ExplainabilityLevel.NONE
