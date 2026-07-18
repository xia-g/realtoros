"""
Literal — typed immutable value objects for DSL.

DSL never works with raw Python types.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Union


@dataclass(frozen=True)
class StringValue:
    value: str


@dataclass(frozen=True)
class IntegerValue:
    value: int


@dataclass(frozen=True)
class DecimalValue:
    value: Decimal


@dataclass(frozen=True)
class BooleanValue:
    value: bool


@dataclass(frozen=True)
class DateValue:
    value: date


@dataclass(frozen=True)
class DateTimeValue:
    value: datetime


@dataclass(frozen=True)
class EnumValue:
    value: str


# Union of all literal types
LiteralValue = Union[
    StringValue,
    IntegerValue,
    DecimalValue,
    BooleanValue,
    DateValue,
    DateTimeValue,
    EnumValue,
]


def to_literal(value: Any) -> LiteralValue:
    """Convert a raw Python value to the corresponding DSL literal."""
    if isinstance(value, str):
        return StringValue(value=value)
    elif isinstance(value, bool):
        return BooleanValue(value=value)
    elif isinstance(value, int):
        return IntegerValue(value=value)
    elif isinstance(value, float):
        return DecimalValue(value=Decimal(str(value)))
    elif isinstance(value, Decimal):
        return DecimalValue(value=value)
    elif isinstance(value, date) and not isinstance(value, datetime):
        return DateValue(value=value)
    elif isinstance(value, datetime):
        return DateTimeValue(value=value)
    else:
        raise ValueError(f"Cannot convert {type(value).__name__} to LiteralValue")
