"""Tests for DealService."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from uuid_extensions import uuid7

from backend.core.exceptions import NotFoundError, ValidationError
from backend.services.deal_service import DealService


@pytest.fixture
def service():
    session = AsyncMock()
    session.flush = AsyncMock()
    service = DealService(session)
    service.repo = AsyncMock()
    return service


class TestCreateDeal:
    async def test_creates_deal_with_participants(self, service):
        service.repo.create = AsyncMock(return_value=MagicMock(id=uuid7()))
        result = await service.create_deal(
            deal_type="buy",
            created_by=uuid7(),
            participants=[uuid7()],
        )
        assert result is not None

    async def test_requires_participants(self, service):
        with pytest.raises(ValidationError):
            await service.create_deal(
                deal_type="buy",
                created_by=uuid7(),
                participants=[],
            )


class TestChangeStatus:
    async def test_valid_transition(self, service):
        deal = MagicMock(status="negotiation")
        service.repo.get = AsyncMock(return_value=deal)
        service.repo.update = AsyncMock(return_value=deal)

        result = await service.change_status(deal.id, "offer_made")
        assert result.status == "offer_made"

    async def test_invalid_transition(self, service):
        deal = MagicMock(status="closed")
        service.repo.get = AsyncMock(return_value=deal)
        with pytest.raises(ValidationError):
            await service.change_status(deal.id, "negotiation")


class TestCloseDeal:
    async def test_close(self, service):
        deal = MagicMock(status="approved")
        service.repo.get = AsyncMock(return_value=deal)
        result = await service.close_deal(deal.id)
        assert result.status == "closed"
