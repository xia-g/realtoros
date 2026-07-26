"""Resolution models — status enum, result dataclass, resolution context.

Defines the contract between resolvers and the consumer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID


class ResolutionStatus(str, Enum):
    """Confidence-based resolution status (ADR-005).

    RESOLVED  — exact match (INN or cadastral) → auto-link.
    AMBIGUOUS — partial match, multiple candidates → needs review.
    NOT_FOUND — no candidate found → create new entity from OCR data.
    """

    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"


@dataclass
class ResolutionResult:
    """Result of resolving a single entity (Property or Client).

    Attributes:
        status: Resolution status.
        entity_id: Resolved or created entity UUID (None for AMBIGUOUS).
        confidence: Human-readable confidence level.
        evidence: Matching evidence for audit trail.
        created: Whether a new entity was created.
        candidate_ids: UUIDs of all candidates considered.
    """

    status: ResolutionStatus
    entity_id: UUID | None
    confidence: str  # "high" | "medium" | "low"
    evidence: list[dict[str, Any]] = field(default_factory=list)
    created: bool = False
    candidate_ids: list[UUID] = field(default_factory=list)


@dataclass
class DealResolutionContext:
    """Aggregate result of resolving all entities for a deal.

    Attributes:
        property_result: Property resolution result.
        buyer_result: Buyer Client resolution result.
        seller_result: Seller Client resolution result.
        resolution_attempt_id: UUID of the logged resolution attempt (optional).
    """

    property_result: ResolutionResult | None = None
    buyer_result: ResolutionResult | None = None
    seller_result: ResolutionResult | None = None
    resolution_attempt_id: UUID | None = None
