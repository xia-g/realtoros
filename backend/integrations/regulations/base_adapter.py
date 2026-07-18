"""Regulation Source Adapter — base interface for all regulation providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class SourceFetchResult:
    """Результат запроса к источнику."""
    documents: list[dict]
    metadata: dict | None = None


class RegulationSourceAdapter(ABC):
    """Базовый адаптер для внешних источников нормативных актов."""

    @abstractmethod
    async def fetch_updates(self, since: str | None = None) -> SourceFetchResult:
        ...

    @abstractmethod
    async def fetch_document(self, document_id: str) -> dict | None:
        ...

    @abstractmethod
    async def get_metadata(self) -> dict:
        ...
