"""
IdentityEvidence — evidence supporting canonical identity.

Immutable value object. Records why an identity is trusted.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IdentityEvidence:
    """Доказательство идентичности. Immutable."""
    source_document_id: str
    confidence: float = 1.0
    detail: str = ""
