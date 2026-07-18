"""
ProjectionQueryService — read-only API for Projections.

Only: get, exists, get_many.
NO predicates, filtering, joins, sorting, aggregation, execution planning.
"""
from __future__ import annotations

from typing import Optional, Sequence

from projection.projection import Projection, ProjectionId, ProjectionType
from projection.projection_digest import ProjectionDigest
from projection.projection_store import ProjectionStore
from projection.exceptions import ProjectionNotFoundError


class ProjectionQueryService:
    """Сервис чтения Projection.

    Исключительно API чтения.
    Не поддерживает: predicates, filtering, joins, sorting, aggregation, planning.
    """

    def __init__(self, store: ProjectionStore) -> None:
        self._store = store

    def get(self, projection_id: ProjectionId) -> Projection:
        """Get single projection by id."""
        return self._store.get(projection_id)

    def exists(self, projection_id: ProjectionId) -> bool:
        """Check if projection exists."""
        return self._store.contains(projection_id)

    def get_many(self, ids: Sequence[ProjectionId]) -> tuple[Projection, ...]:
        """Get multiple projections by ids.

        Silently skips missing projections.
        """
        result: list[Projection] = []
        for pid in ids:
            try:
                result.append(self._store.get(pid))
            except ProjectionNotFoundError:
                pass
        return tuple(result)

    def get_digest(self, projection_id: ProjectionId) -> Optional[ProjectionDigest]:
        """Get stored digest for a projection."""
        return self._store.get_digest(projection_id)
