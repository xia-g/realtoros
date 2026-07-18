"""
FactConfidence — confidence score of a BusinessFact.

Immutable value object. Range [0.0, 1.0].
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FactConfidence:
    """Уверенность в факте. Immutable value object. Range [0.0, 1.0]."""
    value: float

    def __post_init__(self):
        if not (0.0 <= self.value <= 1.0):
            raise ValueError(f"Confidence must be in [0.0, 1.0], got {self.value}")

    def __bool__(self) -> bool:
        return self.value > 0.0

    def __float__(self) -> float:
        return self.value

    @classmethod
    def high(cls) -> FactConfidence:
        return cls(value=0.95)

    @classmethod
    def medium(cls) -> FactConfidence:
        return cls(value=0.75)

    @classmethod
    def low(cls) -> FactConfidence:
        return cls(value=0.50)

    @classmethod
    def from_float(cls, value: float) -> FactConfidence:
        return cls(value=value)
