"""Tests for ClientService."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from uuid_extensions import uuid7

from backend.core.exceptions import NotFoundError, ValidationError
from backend.services.client_service import ClientService


@pytest.fixture
def service():
    session = AsyncMock()
    service = ClientService(session)
    service.repo = AsyncMock()
    return service


class TestCreateClient:
    async def test_creates_client(self, service):
        service.repo.create = AsyncMock(return_value=MagicMock(id=uuid7()))
        result = await service.create_client(full_name="Ivan Ivanov", phone="+79001112233")
        assert result is not None

    async def test_requires_name(self, service):
        with pytest.raises(ValidationError):
            await service.create_client(full_name="")

    async def test_requires_phone_or_email(self, service):
        with pytest.raises(ValidationError):
            await service.create_client(full_name="Ivan")

    async def test_phone_only(self, service):
        service.repo.create = AsyncMock(return_value=MagicMock(id=uuid7()))
        result = await service.create_client(full_name="Ivan", phone="+79000000000")
        assert result is not None


class TestUpdateClient:
    async def test_update(self, service):
        service.repo.update = AsyncMock(return_value=MagicMock(id=uuid7()))
        result = await service.update_client(uuid7(), full_name="New Name")
        assert result is not None

    async def test_not_found(self, service):
        service.repo.update = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await service.update_client(uuid7())


class TestArchiveClient:
    async def test_archive(self, service):
        service.repo.delete = AsyncMock(return_value=True)
        await service.archive_client(uuid7())

    async def test_not_found(self, service):
        service.repo.delete = AsyncMock(return_value=False)
        with pytest.raises(NotFoundError):
            await service.archive_client(uuid7())
