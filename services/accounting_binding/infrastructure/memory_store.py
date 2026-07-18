"""
MemoryProjectionStore — reference implementation of ProjectionStore.

Deterministic. Fully in-memory. Used for tests, local runs, and as
the behavioural reference for all other store implementations.
"""
from __future__ import annotations

from typing import Optional

from projection.projection import Projection, ProjectionId, ProjectionType
from projection.projection_digest import ProjectionDigest
from projection.exceptions import ProjectionNotFoundError
from infrastructure.exceptions import StoreError
from infrastructure.projection_codec import ProjectionCodec


class MemoryProjectionStore:
    """Эталонная реализация ProjectionStore.

    Используется тестами, локальным запуском и как behavioural reference.
    Все остальные реализации должны вести себя идентично.
    """

    def __init__(self) -> None:
        self._data: dict[str, Projection] = {}
        self._digests: dict[str, ProjectionDigest] = {}

    def put(self, projection: Projection) -> None:
        self._data[projection.projection_id.value] = projection

    def get(self, projection_id: ProjectionId) -> Projection:
        p = self._data.get(projection_id.value)
        if p is None:
            raise ProjectionNotFoundError(f"Projection not found: {projection_id.value}")
        return p

    def remove(self, projection_id: ProjectionId) -> bool:
        existed = projection_id.value in self._data
        self._data.pop(projection_id.value, None)
        self._digests.pop(projection_id.value, None)
        return existed

    def contains(self, projection_id: ProjectionId) -> bool:
        return projection_id.value in self._data

    def get_digest(self, projection_id: ProjectionId) -> Optional[ProjectionDigest]:
        return self._digests.get(projection_id.value)

    def put_digest(self, projection_id: ProjectionId, digest: ProjectionDigest) -> None:
        """Store a digest for staleness checking."""
        self._digests[projection_id.value] = digest

    @property
    def count(self) -> int:
        """Total stored projections."""
        return len(self._data)
