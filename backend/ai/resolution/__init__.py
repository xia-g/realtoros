"""Entity resolution — match extracted entities with CRM records.

Pipeline:
1. Exact match (phone, email, cadastral number)
2. Fuzzy match (name similarity)
3. Embedding similarity (requires embeddings)

Thresholds:
- 0.95 auto-link
- 0.75 review queue
- < 0.75 create candidate
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from backend.core.logging import get_logger

logger = get_logger("knowledge")


@dataclass
class ResolutionMatch:
    entity_type: str  # client, property, deal, document, organization
    source: str  # extracted identifier
    target_id: UUID | None = None
    confidence: float = 0.0
    strategy: str = "none"
    auto_link: bool = False
    needs_review: bool = True
    candidate: bool = False


class EntityResolutionService:
    """Match extracted entities to existing CRM records."""

    def __init__(self, session=None):
        self.session = session

    async def resolve_person(self, full_name: str, phone: str = "", email: str = "") -> ResolutionMatch:
        if not self.session:
            return ResolutionMatch(entity_type="client", source=full_name, confidence=0.0)

        from backend.repositories import ClientRepository
        repo = ClientRepository(self.session)

        # Exact match by phone
        if phone:
            client = await repo.find_by_phone(phone)
            if client:
                return ResolutionMatch(
                    entity_type="client",
                    source=phone,
                    target_id=client.id,
                    confidence=0.99,
                    strategy="exact_phone",
                    auto_link=True,
                    needs_review=False,
                )

        # Exact match by email
        if email:
            client = await repo.find_by_email(email)
            if client:
                return ResolutionMatch(
                    entity_type="client",
                    source=email,
                    target_id=client.id,
                    confidence=0.99,
                    strategy="exact_email",
                    auto_link=True,
                    needs_review=False,
                )

        # Fuzzy match by name
        if full_name:
            matches = await repo.find_by_name(full_name, limit=5)
            if matches:
                from difflib import SequenceMatcher
                best = max(matches, key=lambda c: SequenceMatcher(None, full_name.lower(), c.full_name.lower()).ratio())
                score = SequenceMatcher(None, full_name.lower(), best.full_name.lower()).ratio()
                return ResolutionMatch(
                    entity_type="client",
                    source=full_name,
                    target_id=best.id,
                    confidence=round(score, 3),
                    strategy="fuzzy_name",
                    auto_link=score >= 0.95,
                    needs_review=0.75 <= score < 0.95,
                    candidate=score < 0.75,
                )

        return ResolutionMatch(entity_type="client", source=full_name, confidence=0.0, candidate=True)

    async def resolve_property(self, cadastral_number: str = "", address: str = "") -> ResolutionMatch:
        if not self.session or not cadastral_number:
            return ResolutionMatch(entity_type="property", source=cadastral_number or address, confidence=0.0)

        from backend.repositories import PropertyRepository
        repo = PropertyRepository(self.session)
        results = await repo.search_by_text(cadastral_number, limit=5)
        if results:
            return ResolutionMatch(
                entity_type="property",
                source=cadastral_number,
                target_id=results[0].id,
                confidence=0.95,
                strategy="exact_cadastral",
                auto_link=True,
                needs_review=False,
            )

        return ResolutionMatch(entity_type="property", source=cadastral_number, confidence=0.0, candidate=True)