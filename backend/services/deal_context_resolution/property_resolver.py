"""PropertyResolver — resolves a Property from document profile data.

Resolution strategy (priority order):
  1. Cadastral exact match → RESOLVED
  2. Address match → RESOLVED
  3. No match → NOT_FOUND → create new Property from profile
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.property import Property
from backend.services.deal_context_resolution.models import (
    ResolutionResult,
    ResolutionStatus,
)
from backend.services.deal_context_resolution.normalization import (
    normalize_cadastral,
)


class PropertyResolver:
    """Resolves a Property from document profile data.

    Uses direct DB queries on the properties table:
    cadastral_number → address → create new.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve(
        self,
        cadastral_number: str | None = None,
        address: str | None = None,
        property_type: str | None = None,
    ) -> ResolutionResult:
        """Resolve a Property from OCR-extracted data.

        Priority:
          1. Exact cadastral number match → RESOLVED (high confidence)
          2. Address ILIKE match → RESOLVED (medium confidence)
          3. No match → NOT_FOUND → create new Property from profile

        Args:
            cadastral_number: Normalized cadastral number (XX:XX:XXXXXXX:XXXX).
            address: Property address from OCR.
            property_type: Property type (apartment, house, land, etc.).

        Returns:
            ResolutionResult with status, entity_id, confidence, evidence.
        """
        # Normalize canonical forms before matching
        cadastral_number = (
            normalize_cadastral(cadastral_number)
            if cadastral_number
            else cadastral_number
        )

        # Priority 1: Exact cadastral match
        if cadastral_number:
            existing = await self._find_by_cadastral(cadastral_number)
            if existing:
                return ResolutionResult(
                    status=ResolutionStatus.RESOLVED,
                    entity_id=existing.id,
                    confidence="high",
                    evidence=[
                        {
                            "field": "cadastral_number",
                            "value": cadastral_number,
                        }
                    ],
                )

        # Priority 2: Address match (case-insensitive)
        if address:
            existing = await self._find_by_address(address)
            if existing:
                return ResolutionResult(
                    status=ResolutionStatus.RESOLVED,
                    entity_id=existing.id,
                    confidence="medium",
                    evidence=[
                        {
                            "field": "address",
                            "value": address,
                        }
                    ],
                )

        # Priority 3: Create new Property from profile
        return await self._create_from_profile(
            cadastral_number=cadastral_number,
            address=address,
            property_type=property_type,
        )

    async def _find_by_cadastral(
        self, cadastral_number: str
    ) -> Property | None:
        """Find a Property by exact cadastral number match."""
        stmt = select(Property).where(
            Property.cadastral_number == cadastral_number
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _find_by_address(self, address: str) -> Property | None:
        """Find a Property by address ILIKE match."""
        stmt = select(Property).where(
            Property.address.ilike(f"%{address}%")
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _create_from_profile(
        self,
        cadastral_number: str | None = None,
        address: str | None = None,
        property_type: str | None = None,
    ) -> ResolutionResult:
        """Create a new Property from OCR profile data.

        Uses sensible defaults for required fields when profile data
        is incomplete.
        """
        prop = Property(
            cadastral_number=cadastral_number,
            address=address or "Адрес не указан (требуется ручной ввод)",
            property_type=property_type or "apartment",
            title=(
                f"Объект {cadastral_number}"
                if cadastral_number
                else f"Объект по адресу {address}" if address else "Новый объект (требуется ручной ввод)"
            ),
            deal_type="buy",
            price=0,
        )
        self._session.add(prop)
        await self._session.flush()

        return ResolutionResult(
            status=ResolutionStatus.NOT_FOUND,
            entity_id=prop.id,
            confidence="low",
            evidence=[
                {
                    "field": "cadastral_number",
                    "value": cadastral_number,
                },
                {
                    "field": "address",
                    "value": address,
                },
            ],
            created=True,
        )
