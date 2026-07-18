"""
Predicate — immutable typed predicate expression.

Predicate does NOT execute. It only describes a condition.
Forms a tree via composition (AND, OR, NOT).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Sequence, Union

from query.property_reference import PropertyReference
from query.literal import LiteralValue


class PredicateOperator(Enum):
    """Операторы сравнения. Только описание, не исполнение."""
    EQUALS = auto()
    NOT_EQUALS = auto()
    GREATER_THAN = auto()
    GREATER_OR_EQUAL = auto()
    LESS_THAN = auto()
    LESS_OR_EQUAL = auto()
    CONTAINS = auto()
    STARTS_WITH = auto()
    ENDS_WITH = auto()
    EXISTS = auto()
    IN = auto()


@dataclass(frozen=True)
class ComparisonPredicate:
    """Условие сравнения: property operator value."""
    property_ref: PropertyReference
    operator: PredicateOperator
    value: LiteralValue


@dataclass(frozen=True)
class ExistsPredicate:
    """Проверка существования свойства."""
    property_ref: PropertyReference


@dataclass(frozen=True)
class InPredicate:
    """Проверка вхождения в список значений."""
    property_ref: PropertyReference
    values: tuple[LiteralValue, ...]


# Predicate is a union of all predicate types
Predicate = Union[ComparisonPredicate, ExistsPredicate, InPredicate]
