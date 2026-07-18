"""
GraphAttributes — immutable attributes for nodes and edges.

GraphMetadata — immutable metadata for nodes and edges.

Both are pure data. No behavior.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class GraphAttributes:
    """Атрибуты узла или ребра графа. Immutable."""
    label: str = ""
    display_name: str = ""
    tags: tuple[str, ...] = ()
    properties: tuple[tuple[str, str], ...] = ()  # key-value pairs


@dataclass(frozen=True)
class GraphMetadata:
    """Метаданные узла или ребра графа. Immutable."""
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    knowledge_revision_hint: int = 0
    schema_version: int = 1
