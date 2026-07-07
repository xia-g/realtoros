"""
FactId — identity of a BusinessFact.

Immutable value object. Serializable. Hashable.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class FactId:
    """Идентификатор факта. Immutable value object."""
    value: str

    def __bool__(self) -> bool:
        return bool(self.value)

    def __str__(self) -> str:
        return self.value

    @classmethod
    def generate(cls) -> FactId:
        return cls(value=str(uuid.uuid4()))

    @classmethod
    def from_string(cls, value: str) -> FactId:
        if not value or not value.strip():
            raise ValueError("FactId must not be empty")
        return cls(value=value.strip())
