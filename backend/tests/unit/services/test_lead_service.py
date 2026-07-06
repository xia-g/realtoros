"""Tests for LeadService including conversion engine."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from uuid_extensions import uuid7

from backend.core.exceptions import DuplicateEntityError, LeadStateError, NotFoundError
from backend.models.lead import Lead
from backend.services.lead_service import LeadService


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def lead_service(mock_session):
    service = LeadService(mock_session)
    service.lead_repo = AsyncMock()
    service.client_repo = AsyncMock()
    service.client_service = AsyncMock()
    return service


def make_lead(**kwargs):
    defaults = dict(
        id=uuid7(),
        source="telegram",
        source_id="tg_123",
        full_name="Test Lead",
        phone="+79001234567",
        email=None,
        status="new",
        score=0.0,
        priority="cold",
        interest_type="buy",
        deleted_at=None,
    )
    defaults.update(kwargs)
    return MagicMock(spec=Lead, **defaults)


class TestCreateLead:
    async def test_creates_lead_successfully(self, lead_service):
        lead_service.lead_repo.find_by_source = AsyncMock(return_value=None)
        lead_service.lead_repo.find_by_phone = AsyncMock(return_value=[])
        lead_service.lead_repo.create = AsyncMock(return_value=make_lead())

        result = await lead_service.create_lead(source="telegram", source_id="tg_123")
        assert result is not None
        lead_service.lead_repo.create.assert_awaited_once()

    async def test_raises_on_duplicate_source(self, lead_service):
        existing = make_lead()
        lead_service.lead_repo.find_by_source = AsyncMock(return_value=existing)

        with pytest.raises(DuplicateEntityError):
            await lead_service.create_lead(source="telegram", source_id="tg_123")

    async def test_requires_nothing_but_source(self, lead_service):
        lead_service.lead_repo.find_by_source = AsyncMock(return_value=None)
        lead_service.lead_repo.find_by_phone = AsyncMock(return_value=[])
        lead_service.lead_repo.create = AsyncMock(return_value=make_lead(source="manual"))

        result = await lead_service.create_lead(source="manual")
        assert result is not None


class TestChangeStatus:
    async def test_valid_transition(self, lead_service):
        lead = make_lead(status="new")
        lead_service.lead_repo.get = AsyncMock(return_value=lead)

        result = await lead_service.change_status(lead.id, "contact_made")
        assert result.status == "contact_made"

    async def test_invalid_transition(self, lead_service):
        lead = make_lead(status="converted")
        lead_service.lead_repo.get = AsyncMock(return_value=lead)

        with pytest.raises(LeadStateError):
            await lead_service.change_status(lead.id, "new")

    async def test_not_found(self, lead_service):
        lead_service.lead_repo.get = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await lead_service.change_status(uuid7(), "contact_made")

    async def test_same_status_noop(self, lead_service):
        lead = make_lead(status="new")
        lead_service.lead_repo.get = AsyncMock(return_value=lead)

        result = await lead_service.change_status(lead.id, "new")
        assert result.status == "new"


class TestScoreLead:
    async def test_valid_score(self, lead_service):
        lead = make_lead(score=0.0)
        lead_service.lead_repo.get = AsyncMock(return_value=lead)

        result = await lead_service.score_lead(lead.id, 0.75)
        assert result.score == 0.75

    async def test_invalid_score_too_high(self, lead_service):
        with pytest.raises(Exception):
            await lead_service.score_lead(uuid7(), 1.5)


class TestQualify:
    async def test_qualify_lead(self, lead_service):
        lead = make_lead(status="new")
        lead_service.lead_repo.get = AsyncMock(return_value=lead)

        result = await lead_service.qualify_lead(lead.id, uuid7())
        assert result.status == "qualified"


class TestAssignLead:
    async def test_assign(self, lead_service):
        lead = make_lead()
        user_id = uuid7()
        lead_service.lead_repo.get = AsyncMock(return_value=lead)

        result = await lead_service.assign_lead(lead.id, user_id)
        assert result is not None


class TestMergeLeads:
    async def test_merge(self, lead_service):
        primary = make_lead(phone="+79000000001")
        secondary = make_lead(phone="+79000000002", email="test@example.com")
        lead_service.lead_repo.get = AsyncMock(side_effect=[primary, secondary])

        result = await lead_service.merge_leads(primary.id, secondary.id)
        assert result is not None


class TestConvertLead:
    async def test_converts_qualified_lead(self, lead_service):
        lead = make_lead(status="qualified")
        lead_service.lead_repo.get = AsyncMock(return_value=lead)
        lead_service.client_service.create_client = AsyncMock(
            return_value=MagicMock(id=uuid7())
        )

        result = await lead_service.convert_lead(lead.id, converted_by=uuid7())
        assert result.lead.status == "converted"
        assert result.client is not None

    async def test_fails_non_qualified(self, lead_service):
        lead = make_lead(status="new")
        lead_service.lead_repo.get = AsyncMock(return_value=lead)

        with pytest.raises(LeadStateError):
            await lead_service.convert_lead(lead.id, converted_by=uuid7())
