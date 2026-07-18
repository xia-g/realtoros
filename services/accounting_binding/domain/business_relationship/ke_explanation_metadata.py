"""
ExplanationMetadata — metadata for GraphExplanation.

Immutable. Infrastructure fields only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ExplanationMetadata:
    """Метаданные объяснения. Immutable."""
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    knowledge_revision_hint: int = 0
    schema_version: int = 1
