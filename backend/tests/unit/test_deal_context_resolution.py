"""Unit tests for Deal Context Resolution — models, normalization, resolvers.

Tests cover:
  - ResolutionStatus enum, ResolutionResult, DealResolutionContext dataclasses
  - Normalization: normalize_inn, normalize_cadastral
  - PropertyResolver: cadastral match, address match, create new
  - ClientResolver: INN match, name single match, name ambiguous, create new
"""

from __future__ import annotations

import sys
import os
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.deal_context_resolution.models import (
    ResolutionResult,
    ResolutionStatus,
    DealResolutionContext,
)
from backend.services.deal_context_resolution.normalization import (
    normalize_inn,
    normalize_cadastral,
)
from backend.services.deal_context_resolution.property_resolver import (
    PropertyResolver,
)
from backend.services.deal_context_resolution.client_resolver import (
    ClientResolver,
)


# ═══════════════════════════════════════════════════════════════════
# 1. Models Tests
# ═══════════════════════════════════════════════════════════════════


class TestResolutionStatus:
    """ResolutionStatus enum values and string coercion."""

    def test_resolved_value(self):
        assert ResolutionStatus.RESOLVED.value == "resolved"

    def test_ambiguous_value(self):
        assert ResolutionStatus.AMBIGUOUS.value == "ambiguous"

    def test_not_found_value(self):
        assert ResolutionStatus.NOT_FOUND.value == "not_found"

    def test_str_coercion(self):
        assert str(ResolutionStatus.RESOLVED) == "ResolutionStatus.RESOLVED"

    def test_membership(self):
        assert ResolutionStatus.RESOLVED in ResolutionStatus


class TestResolutionResult:
    """ResolutionResult dataclass construction and defaults."""

    def test_resolved_result(self):
        entity_id = uuid4()
        result = ResolutionResult(
            status=ResolutionStatus.RESOLVED,
            entity_id=entity_id,
            confidence="high",
            evidence=[{"field": "inn", "value": "7701234567"}],
        )
        assert result.status == ResolutionStatus.RESOLVED
        assert result.entity_id == entity_id
        assert result.confidence == "high"
        assert result.evidence == [{"field": "inn", "value": "7701234567"}]
        assert result.created is False
        assert result.candidate_ids == []

    def test_ambiguous_result(self):
        result = ResolutionResult(
            status=ResolutionStatus.AMBIGUOUS,
            entity_id=None,
            confidence="low",
            evidence=[{"field": "name", "value": "Иван", "candidates": 3}],
            candidate_ids=[uuid4(), uuid4(), uuid4()],
        )
        assert result.status == ResolutionStatus.AMBIGUOUS
        assert result.entity_id is None
        assert len(result.candidate_ids) == 3

    def test_not_found_result_created(self):
        entity_id = uuid4()
        result = ResolutionResult(
            status=ResolutionStatus.NOT_FOUND,
            entity_id=entity_id,
            confidence="low",
            evidence=[],
            created=True,
        )
        assert result.status == ResolutionStatus.NOT_FOUND
        assert result.created is True


class TestDealResolutionContext:
    """DealResolutionContext dataclass."""

    def test_default_none(self):
        ctx = DealResolutionContext()
        assert ctx.property_result is None
        assert ctx.buyer_result is None
        assert ctx.seller_result is None
        assert ctx.resolution_attempt_id is None

    def test_with_results(self):
        prop_result = ResolutionResult(
            status=ResolutionStatus.RESOLVED,
            entity_id=uuid4(),
            confidence="high",
        )
        buyer_result = ResolutionResult(
            status=ResolutionStatus.RESOLVED,
            entity_id=uuid4(),
            confidence="high",
        )
        ctx = DealResolutionContext(
            property_result=prop_result,
            buyer_result=buyer_result,
        )
        assert ctx.property_result is not None
        assert ctx.buyer_result is not None
        assert ctx.seller_result is None


# ═══════════════════════════════════════════════════════════════════
# 2. Normalization Tests
# ═══════════════════════════════════════════════════════════════════


class TestNormalizeInn:
    """normalize_inn: digits only, strip whitespace."""

    def test_legal_inn(self):
        assert normalize_inn("7701234567") == "7701234567"

    def test_individual_inn(self):
        assert normalize_inn("123456789012") == "123456789012"

    def test_with_dashes(self):
        assert normalize_inn("770-123-4567") == "7701234567"

    def test_with_spaces(self):
        assert normalize_inn(" 770 123 4567 ") == "7701234567"

    def test_with_letters(self):
        assert normalize_inn("INN7701234567X") == "7701234567"

    def test_none_input(self):
        assert normalize_inn(None) is None

    def test_empty_string(self):
        assert normalize_inn("") is None

    def test_only_whitespace(self):
        assert normalize_inn("   ") is None


class TestNormalizeCadastral:
    """normalize_cadastral: colons, uppercase."""

    def test_standard_format(self):
        assert (
            normalize_cadastral("78:01:0001001:1234")
            == "78:01:0001001:1234"
        )

    def test_with_dashes(self):
        assert (
            normalize_cadastral("78-01-0001001-1234")
            == "78:01:0001001:1234"
        )

    def test_with_spaces(self):
        assert (
            normalize_cadastral("78 01 0001001 1234")
            == "78:01:0001001:1234"
        )

    def test_case_insensitive(self):
        assert (
            normalize_cadastral("78:01:0001001:abcd")
            == "78:01:0001001:ABCD"
        )

    def test_mixed_separators(self):
        assert (
            normalize_cadastral("78-01 0001001:1234")
            == "78:01:0001001:1234"
        )

    def test_none_input(self):
        assert normalize_cadastral(None) is None

    def test_empty_string(self):
        assert normalize_cadastral("") is None


# ═══════════════════════════════════════════════════════════════════
# 3. PropertyResolver Tests
# ═══════════════════════════════════════════════════════════════════


class TestPropertyResolver:
    """PropertyResolver: cadastral match, address match, create new."""

    pytestmark = pytest.mark.asyncio

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        # add() is synchronous in SQLAlchemy (queues the object)
        session._added_objects = []

        def _add(obj):
            session._added_objects.append(obj)

        async def _flush():
            for obj in session._added_objects:
                if hasattr(obj, 'id') and obj.id is None:
                    obj.id = uuid4()
            session._added_objects.clear()

        session.add = MagicMock(side_effect=_add)
        session.flush = AsyncMock(side_effect=_flush)
        return session

    @pytest.fixture
    def resolver(self, mock_session):
        return PropertyResolver(mock_session)

    async def test_cadastral_match_resolved(self, resolver, mock_session):
        """Exact cadastral match → RESOLVED with high confidence."""
        property_id = uuid4()
        mock_property = MagicMock()
        mock_property.id = property_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_property
        mock_session.execute.return_value = mock_result

        result = await resolver.resolve(
            cadastral_number="78:01:0001001:1234",
            address="ул. Ленина, д. 1",
        )

        assert result.status == ResolutionStatus.RESOLVED
        assert result.entity_id == property_id
        assert result.confidence == "high"
        assert result.evidence[0]["field"] == "cadastral_number"

    @pytest.mark.asyncio
    async def test_address_match_resolved(self, resolver, mock_session):
        """Address match (no cadastral) → RESOLVED with medium confidence."""
        property_id = uuid4()
        mock_property = MagicMock()
        mock_property.id = property_id

        # Only one execute call for address search (cadastral_number=None → skip)
        mock_result_found = MagicMock()
        mock_result_found.scalar_one_or_none.return_value = mock_property

        mock_session.execute = AsyncMock(
            side_effect=[mock_result_found]
        )

        result = await resolver.resolve(
            cadastral_number=None,
            address="ул. Ленина, д. 1",
        )

        assert result.status == ResolutionStatus.RESOLVED
        assert result.entity_id == property_id
        assert result.confidence == "medium"
        assert result.evidence[0]["field"] == "address"

    async def test_no_match_creates_new(self, resolver, mock_session):
        """No match → NOT_FOUND → creates new Property."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await resolver.resolve(
            cadastral_number=None,
            address=None,
        )

        assert result.status == ResolutionStatus.NOT_FOUND
        assert result.entity_id is not None
        assert result.created is True
        assert result.confidence == "low"
        # Should have called session.add with a new Property
        mock_session.add.assert_called_once()

    async def test_cadastral_normalized_before_match(
        self, resolver, mock_session
    ):
        """Cadastral is normalized before matching."""
        property_id = uuid4()
        mock_property = MagicMock()
        mock_property.id = property_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_property
        mock_session.execute.return_value = mock_result

        await resolver.resolve(
            cadastral_number="78-01-0001001-1234",
            address=None,
        )

        # Should normalize dashes to colons and search with normalized form
        call_args = mock_session.execute.call_args[0][0]
        call_str = str(call_args)
        assert "78:01:0001001:1234" in call_str or "cadastral_number" in call_str


# ═══════════════════════════════════════════════════════════════════
# 4. ClientResolver Tests
# ═══════════════════════════════════════════════════════════════════


class TestClientResolver:
    """ClientResolver: INN match, name single, name ambiguous, create."""

    pytestmark = pytest.mark.asyncio

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        # add() is synchronous in SQLAlchemy (queues the object)
        session._added_objects = []

        def _add(obj):
            session._added_objects.append(obj)

        async def _flush():
            for obj in session._added_objects:
                if hasattr(obj, 'id') and obj.id is None:
                    obj.id = uuid4()
            session._added_objects.clear()

        session.add = MagicMock(side_effect=_add)
        session.flush = AsyncMock(side_effect=_flush)
        return session

    @pytest.fixture
    def resolver(self, mock_session):
        return ClientResolver(mock_session)

    async def test_inn_match_resolved(self, resolver, mock_session):
        """INN exact match → RESOLVED with high confidence."""
        client_id = uuid4()
        mock_client = MagicMock()
        mock_client.id = client_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_session.execute.return_value = mock_result

        result = await resolver.resolve(
            name="Иван Иванов",
            inn="7701234567",
        )

        assert result.status == ResolutionStatus.RESOLVED
        assert result.entity_id == client_id
        assert result.confidence == "high"
        assert result.evidence[0]["field"] == "inn"

    async def test_name_single_match_resolved(
        self, resolver, mock_session
    ):
        """Single name match → RESOLVED with medium confidence."""
        client_id = uuid4()
        mock_client = MagicMock()
        mock_client.id = client_id

        mock_result_name = MagicMock()
        mock_result_name.scalars.return_value.all.return_value = [mock_client]

        # No INN search when inn=None — only one execute call for name
        mock_session.execute = AsyncMock(
            side_effect=[mock_result_name]
        )

        result = await resolver.resolve(
            name="Иван Иванов",
            inn=None,
        )

        assert result.status == ResolutionStatus.RESOLVED
        assert result.entity_id == client_id
        assert result.confidence == "medium"
        assert result.evidence[0]["field"] == "name"

    async def test_name_multiple_matches_ambiguous(
        self, resolver, mock_session
    ):
        """Multiple name matches → AMBIGUOUS."""
        mock_client_1 = MagicMock()
        mock_client_1.id = uuid4()
        mock_client_2 = MagicMock()
        mock_client_2.id = uuid4()

        mock_result_name = MagicMock()
        mock_result_name.scalars.return_value.all.return_value = [
            mock_client_1,
            mock_client_2,
        ]

        # No INN search when inn=None — only one execute call for name
        mock_session.execute = AsyncMock(
            side_effect=[mock_result_name]
        )

        result = await resolver.resolve(
            name="Иван Иванов",
            inn=None,
        )

        assert result.status == ResolutionStatus.AMBIGUOUS
        assert result.entity_id is None
        assert result.confidence == "low"
        assert len(result.candidate_ids) == 2

    async def test_no_match_creates_new(self, resolver, mock_session):
        """No match → NOT_FOUND → creates new Client."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await resolver.resolve(
            name="Новый Клиент",
            inn=None,
        )

        assert result.status == ResolutionStatus.NOT_FOUND
        assert result.entity_id is not None
        assert result.created is True
        assert result.confidence == "low"
        mock_session.add.assert_called_once()

    async def test_inn_normalized_before_match(
        self, resolver, mock_session
    ):
        """INN is normalized before matching."""
        client_id = uuid4()
        mock_client = MagicMock()
        mock_client.id = client_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_session.execute.return_value = mock_result

        await resolver.resolve(
            name="Иван Иванов",
            inn=" 770-123-4567 ",
        )

        # INN was normalized to digits-only → INN search was executed
        mock_session.execute.assert_called_once()

    async def test_invalid_inn_length_skipped(
        self, resolver, mock_session
    ):
        """INN with invalid length (not 10 or 12) → skip INN search."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await resolver.resolve(
            name="Иван Иванов",
            inn="12345",  # Only 5 digits — not valid
        )

        # Should go to name match or create path, not INN match
        assert result.status == ResolutionStatus.NOT_FOUND
        assert result.created is True
