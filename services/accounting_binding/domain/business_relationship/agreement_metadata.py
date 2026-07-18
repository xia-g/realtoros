"""
AgreementMetadata — non-business metadata for Agreement.

Immutable value object. Contains only infrastructure-relevant fields.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class AgreementMetadata:
    """Метаданные соглашения. Не бизнес-логика."""
    source_document_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    confidence: float = 1.0
