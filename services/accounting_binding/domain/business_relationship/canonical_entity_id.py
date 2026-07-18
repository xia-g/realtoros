"""
CanonicalEntityId — identity of a CanonicalEntity.

Immutable value object. Serializable. Hashable.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class CanonicalEntityId:
    """Идентификатор канонической сущности. Immutable value object."""
    value: str

    def __bool__(self) -> bool:
        return bool(self.value)

    def __str__(self) -> str:
        return self.value

    @classmethod
    def generate(cls) -> CanonicalEntityId:
        return cls(value=str(uuid.uuid4()))

    @classmethod
    def from_string(cls, value: str) -> CanonicalEntityId:
        if not value or not value.strip():
            raise ValueError("CanonicalEntityId must not be empty")
        return cls(value=value.strip())
