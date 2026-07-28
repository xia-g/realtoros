"""DealContextResolver — orchestrates resolution of all deal entities.

Orchestrates resolution of:
  - Property (cadastral → address → create)
  - Buyer Client (INN → name → create)
  - Seller Client (INN → name → create)

Uses PropertyResolver and ClientResolver for individual entity resolution.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.deal import Deal
from backend.services.deal_context_resolution.client_resolver import (
    ClientResolver,
)
from backend.services.deal_context_resolution.models import (
    DealResolutionContext,
    ResolutionResult,
    ResolutionStatus,
)
from backend.services.deal_context_resolution.property_resolver import (
    PropertyResolver,
)
from backend.services.deal_context_resolution.application_service import (
    DealApplicationService,
)


class DealContextResolver:
    """Orchestrates resolution of Property, buyer Client, and seller Client.

    Delegates entity-level resolution to PropertyResolver and ClientResolver,
    then applies results via DealApplicationService.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._property_resolver = PropertyResolver(session)
        self._client_resolver = ClientResolver(session)
        self._app_service = DealApplicationService(session)

    async def resolve(
        self,
        deal: Deal,
        profile: dict,
    ) -> DealResolutionContext:
        """Resolve all entities for a deal from document profile data.

        Args:
            deal: The target Deal to enrich.
            profile: Document profile with sections containing
                     property, parties, and financial data.

        Returns:
            DealResolutionContext with all resolution results.
        """
        sections = profile.get("profile", {}).get("sections", {})
        parties = sections.get("parties", {})
        property_data = sections.get("property", {})

        # Resolve property
        property_result = await self._property_resolver.resolve(
            cadastral_number=property_data.get("cadastral_number"),
            address=property_data.get("address"),
            property_type=property_data.get("property_type"),
        )

        # Resolve buyer
        buyer = parties.get("buyer", {})
        buyer_result = await self._client_resolver.resolve(
            name=buyer.get("name"),
            inn=buyer.get("inn"),
            party_type=buyer.get("type"),
        )

        # Resolve seller
        seller = parties.get("seller", {})
        seller_result = await self._client_resolver.resolve(
            name=seller.get("name"),
            inn=seller.get("inn"),
            party_type=seller.get("type"),
        )

        return DealResolutionContext(
            property_result=property_result,
            buyer_result=buyer_result,
            seller_result=seller_result,
        )

    async def apply(
        self,
        deal: Deal,
        result: DealResolutionContext,
    ) -> None:
        """Apply resolution results to the deal.

        Creates/resolves participants and updates deal fields.
        """
        # Attach property if resolved or created
        if result.property_result and result.property_result.entity_id:
            await self._app_service.attach_property(
                deal.id,
                result.property_result.entity_id,
            )

        # Add buyer participant
        if result.buyer_result and result.buyer_result.entity_id:
            await self._app_service.add_participant(
                deal.id,
                result.buyer_result.entity_id,
                role="buyer",
            )

        # Add seller participant
        if result.seller_result and result.seller_result.entity_id:
            await self._app_service.add_participant(
                deal.id,
                result.seller_result.entity_id,
                role="seller",
            )
