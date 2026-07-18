"""
FactValue — typed value of a BusinessFact.

Immutable value object. Supports string, numeric, date values.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class FactValue:
    """Типизированное значение факта. Immutable."""
    string: str | None = None
    numeric: Decimal | None = None
    date: date | None = None

    def __bool__(self) -> bool:
        return self.string is not None or self.numeric is not None or self.date is not None

    def __str__(self) -> str:
        if self.string is not None:
            return self.string
        if self.numeric is not None:
            return str(self.numeric)
        if self.date is not None:
            return self.date.isoformat()
        return ""

    @classmethod
    def from_str(cls, value: str) -> FactValue:
        return cls(string=value)

    @classmethod
    def from_decimal(cls, value: Decimal) -> FactValue:
        return cls(numeric=value)

    @classmethod
    def from_date(cls, value: date) -> FactValue:
        return cls(date=value)
