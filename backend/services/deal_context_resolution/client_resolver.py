"""ClientResolver — resolves a Client (buyer/seller) from document profile data.

Resolution strategy (priority order):
  1. INN exact match → RESOLVED (high confidence)
  2. Name match → single candidate → RESOLVED (medium confidence)
  3. Name match → multiple candidates → AMBIGUOUS (needs review)
  4. No match → NOT_FOUND → create new Client from profile
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.client import Client
from backend.services.deal_context_resolution.models import (
    ResolutionResult,
    ResolutionStatus,
)
from backend.services.deal_context_resolution.normalization import (
    normalize_inn,
)


class ClientResolver:
    """Resolves a Client (buyer/seller) from document profile data.

    Uses direct DB queries on the clients table:
    INN → name → multiple candidates → create new.
    """

    INN_LENGTHS = {10, 12}  # Legal (10) and individual (12) INN

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve(
        self,
        name: str | None = None,
        inn: str | None = None,
        party_type: str | None = None,
    ) -> ResolutionResult:
        """Resolve a Client from OCR-extracted party data.

        Priority:
          1. INN exact match → RESOLVED (high confidence)
          2. Single name match → RESOLVED (medium confidence)
          3. Multiple name matches → AMBIGUOUS (needs operator review)
          4. No match → NOT_FOUND → create new Client from profile

        Args:
            name: Full name of the party.
            inn: INN (10 digits legal, 12 digits individual).
            party_type: Party type ("legal" or "individual").

        Returns:
            ResolutionResult with status, entity_id, confidence, evidence.
        """
        # Normalize INN before matching
        inn = normalize_inn(inn) if inn else inn

        # Priority 1: INN exact match
        if inn and len(inn) in self.INN_LENGTHS:
            existing = await self._find_by_inn(inn)
            if existing:
                return ResolutionResult(
                    status=ResolutionStatus.RESOLVED,
                    entity_id=existing.id,
                    confidence="high",
                    evidence=[
                        {
                            "field": "inn",
                            "value": inn,
                        }
                    ],
                )

        # Priority 2: Name match
        if name:
            candidates = await self._find_by_name(name)
            if len(candidates) == 1:
                return ResolutionResult(
                    status=ResolutionStatus.RESOLVED,
                    entity_id=candidates[0].id,
                    confidence="medium",
                    evidence=[
                        {
                            "field": "name",
                            "value": name,
                        }
                    ],
                    candidate_ids=[c.id for c in candidates],
                )
            elif len(candidates) > 1:
                return ResolutionResult(
                    status=ResolutionStatus.AMBIGUOUS,
                    entity_id=None,
                    confidence="low",
                    evidence=[
                        {
                            "field": "name",
                            "value": name,
                            "candidates": len(candidates),
                        }
                    ],
                    candidate_ids=[c.id for c in candidates],
                )

        # Priority 3: Create new Client from profile
        return await self._create_from_profile(
            name=name, inn=inn, party_type=party_type
        )

    async def _find_by_inn(self, inn: str) -> Client | None:
        """Find a Client by exact INN match."""
        stmt = select(Client).where(Client.inn == inn)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _find_by_name(self, name: str) -> list[Client]:
        """Find Clients by name ILIKE match."""
        stmt = select(Client).where(
            Client.full_name.ilike(f"%{name}%")
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _create_from_profile(
        self,
        name: str | None = None,
        inn: str | None = None,
        party_type: str | None = None,
    ) -> ResolutionResult:
        """Create a new Client from OCR profile data.

        Uses sensible defaults for required fields when profile data
        is incomplete.
        """
        client = Client(
            inn=inn,
            full_name=name or "Не указано (требуется ручной ввод)",
            type="buyer" if party_type != "legal" else "legal",
            status="lead",
        )
        self._session.add(client)
        await self._session.flush()

        return ResolutionResult(
            status=ResolutionStatus.NOT_FOUND,
            entity_id=client.id,
            confidence="low",
            evidence=[
                {
                    "field": "name",
                    "value": name,
                },
                {
                    "field": "inn",
                    "value": inn,
                },
            ],
            created=True,
        )
