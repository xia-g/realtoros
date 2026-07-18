"""Query Engine custom exceptions."""
from __future__ import annotations


class QueryEngineError(Exception):
    """Base Query Engine error."""


class PlanningError(QueryEngineError):
    """Query planning failed."""


class ExecutionError(QueryEngineError):
    """Query execution failed."""


class ResolutionError(QueryEngineError):
    """Projection resolution failed."""


class UnsupportedStrategyError(QueryEngineError):
    """Strategy not supported for the given query."""


class ResultAssemblyError(QueryEngineError):
    """Result assembly failed."""
