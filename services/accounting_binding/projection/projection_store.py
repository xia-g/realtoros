"""
ProjectionStore Protocol — pure abstraction for projection storage.

No implementation. No Database. No Repository awareness.

Only four operations: put, get, remove, contains.
"""
from __future__ import annotations

from typing import Protocol as TypedProtocol, Optional

from projection.projection import Projection, ProjectionId, ProjectionType
from projection.projection_digest import ProjectionDigest
from projection.exceptions import ProjectionNotFoundError


class ProjectionStore(TypedProtocol):
    """Протокол хранилища Projection.

    Store не является Repository.
    Store не знает Domain.
    Store хранит только Projection.

    Никакой реализации хранения — только протокол.
    """

    def put(self, projection: Projection) -> None:
        """Store a projection.

        Overwrites existing projection with same id.
        """
        ...

    def get(self, projection_id: ProjectionId) -> Projection:
        """Get projection by id.

        Raises ProjectionNotFoundError if not found.
        """
        ...

    def remove(self, projection_id: ProjectionId) -> bool:
        """Remove projection. Returns True if existed."""
        ...

    def contains(self, projection_id: ProjectionId) -> bool:
        """Check if projection exists."""
        ...

    def get_digest(self, projection_id: ProjectionId) -> Optional[ProjectionDigest]:
        """Get stored digest for a projection, if exists."""
        ...
