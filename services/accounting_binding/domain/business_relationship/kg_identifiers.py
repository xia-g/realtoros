"""
GraphNodeId — identity of a Knowledge Graph node.

Immutable value object. Serializable. Hashable.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class GraphNodeId:
    """Идентификатор узла графа. Immutable value object."""
    value: str

    def __bool__(self) -> bool:
        return bool(self.value)

    def __str__(self) -> str:
        return self.value

    @classmethod
    def generate(cls) -> GraphNodeId:
        return cls(value=str(uuid.uuid4()))

    @classmethod
    def from_string(cls, value: str) -> GraphNodeId:
        if not value or not value.strip():
            raise ValueError("GraphNodeId must not be empty")
        return cls(value=value.strip())


@dataclass(frozen=True)
class GraphEdgeId:
    """Идентификатор ребра графа. Immutable value object."""
    value: str

    def __bool__(self) -> bool:
        return bool(self.value)

    def __str__(self) -> str:
        return self.value

    @classmethod
    def generate(cls) -> GraphEdgeId:
        return cls(value=str(uuid.uuid4()))

    @classmethod
    def from_string(cls, value: str) -> GraphEdgeId:
        if not value or not value.strip():
            raise ValueError("GraphEdgeId must not be empty")
        return cls(value=value.strip())
