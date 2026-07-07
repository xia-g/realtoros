"""
ProvenanceId — identity of a KnowledgeProvenance record.

Immutable value object. Serializable. Hashable.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class ProvenanceId:
    """Идентификатор происхождения. Immutable value object."""
    value: str

    def __bool__(self) -> bool:
        return bool(self.value)

    def __str__(self) -> str:
        return self.value

    @classmethod
    def generate(cls) -> ProvenanceId:
        return cls(value=str(uuid.uuid4()))

    @classmethod
    def from_string(cls, value: str) -> ProvenanceId:
        if not value or not value.strip():
            raise ValueError("ProvenanceId must not be empty")
        return cls(value=value.strip())