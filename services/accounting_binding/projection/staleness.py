"""
StalenessService — determines freshness of Projections without accessing Domain.

States: Fresh, Stale, Missing.
Works exclusively with Digest.
"""
from __future__ import annotations

from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional

from projection.projection import Projection, ProjectionId, ProjectionType
from projection.projection_digest import ProjectionDigest, ProjectionDigestResult
from projection.projection_store import ProjectionStore


class StalenessState(Enum):
    """Состояние актуальности проекции."""
    FRESH = auto()
    STALE = auto()
    MISSING = auto()


@dataclass(frozen=True)
class StalenessResult:
    """Результат проверки актуальности."""
    state: StalenessState
    projection_id: ProjectionId
    stored_digest: ProjectionDigest
    current_digest: ProjectionDigest
    reason: str = ""


class StalenessService:
    """Сервис определения актуальности Projection.

    Не обращается к Domain. Работает только с Digest.
    """

    def __init__(self, store: ProjectionStore) -> None:
        self._store = store

    def check(
        self,
        projection_id: ProjectionId,
        current_digest: ProjectionDigest,
    ) -> StalenessResult:
        """Check freshness of a projection.

        Args:
            projection_id: идентификатор проекции
            current_digest: текущий дайджест (из текущей Revision)

        Returns:
            StalenessResult with Fresh/Stale/Missing state.
        """
        stored_digest = self._store.get_digest(projection_id)

        if stored_digest is None:
            return StalenessResult(
                state=StalenessState.MISSING,
                projection_id=projection_id,
                stored_digest=ProjectionDigest.empty(),
                current_digest=current_digest,
                reason="Projection not found in store",
            )

        if stored_digest == current_digest:
            return StalenessResult(
                state=StalenessState.FRESH,
                projection_id=projection_id,
                stored_digest=stored_digest,
                current_digest=current_digest,
            )

        return StalenessResult(
            state=StalenessState.STALE,
            projection_id=projection_id,
            stored_digest=stored_digest,
            current_digest=current_digest,
            reason=f"Revision mismatch: stored={stored_digest.revision_number}, current={current_digest.revision_number}",
        )

    def check_many(
        self,
        checks: tuple[tuple[ProjectionId, ProjectionDigest], ...],
    ) -> tuple[StalenessResult, ...]:
        """Check freshness for multiple projections."""
        return tuple(
            self.check(pid, digest) for pid, digest in checks
        )

    def is_fresh(self, projection_id: ProjectionId, current_digest: ProjectionDigest) -> bool:
        """Quick check: is projection fresh?"""
        return self.check(projection_id, current_digest).state == StalenessState.FRESH
