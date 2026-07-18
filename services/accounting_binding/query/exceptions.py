"""Query DSL custom exceptions."""
from __future__ import annotations


class QueryError(Exception):
    """Base Knowledge Query DSL error."""


class InvalidQueryError(QueryError):
    """Query structure is invalid."""


class InvalidPredicateError(QueryError):
    """Predicate is invalid for the given target or property."""


class UnknownPropertyError(QueryError):
    """Property reference does not exist on the target."""


class InvalidReturnShapeError(QueryError):
    """Return shape is incompatible with the query."""


class ValidationError(QueryError):
    """Query validation failed."""
