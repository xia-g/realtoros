"""
PredicateComposition — immutable tree of AND / OR / NOT.

All compositions are immutable. Forms a predicate tree.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Union

from query.predicate import Predicate


# Forward declaration
class _PredicateNode:
    """Base class for composition nodes."""
    pass


@dataclass(frozen=True)
class And:
    """Logical AND of multiple predicates."""
    conditions: tuple[Predicate, ...]

    def __post_init__(self) -> None:
        if len(self.conditions) < 2:
            raise ValueError("AND requires at least 2 conditions")


@dataclass(frozen=True)
class Or:
    """Logical OR of multiple predicates."""
    conditions: tuple[Predicate, ...]

    def __post_init__(self) -> None:
        if len(self.conditions) < 2:
            raise ValueError("OR requires at least 2 conditions")


@dataclass(frozen=True)
class Not:
    """Logical NOT of a single predicate."""
    condition: Predicate


# ComposedPredicate is a union of all composition types
ComposedPredicate = Union[And, Or, Not]

# Any predicate in the DSL is either a leaf Predicate or a ComposedPredicate
QueryPredicate = Union[Predicate, ComposedPredicate]
