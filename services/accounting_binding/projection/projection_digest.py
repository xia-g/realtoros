"""
ProjectionDigest — deterministic digest for freshness tracking.

Built from KnowledgeRevision. Immutable.
Allows determining if a Projection matches the current knowledge state
without full rebuild.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ProjectionDigest:
    """Детерминированный дайджест проекции.

    Строится из KnowledgeRevision и позволяет определить,
    соответствует ли Projection текущему состоянию Knowledge
    без полного перестроения.
    """
    revision_id: str
    revision_number: int
    graph_hash: str
    metadata_hash: str

    @classmethod
    def from_revision(cls, revision: object) -> ProjectionDigest:
        """Build digest from a KnowledgeRevision.

        This is the ONLY place where Digest touches Domain.
        """
        rid = str(getattr(revision, 'revision_id', ''))
        rn = int(getattr(getattr(revision, 'revision_number', None), 'number', 0))
        snapshot = getattr(revision, 'snapshot', None) or None

        if snapshot is not None:
            graph = getattr(snapshot, 'graph', None)
            graph_hash = str(hash(graph)) if graph is not None else '0'
        else:
            graph_hash = '0'

        meta = getattr(revision, 'metadata', None)
        metadata_hash = str(hash(meta)) if meta is not None else '0'

        return cls(
            revision_id=rid,
            revision_number=rn,
            graph_hash=graph_hash,
            metadata_hash=metadata_hash,
        )

    @classmethod
    def empty(cls) -> ProjectionDigest:
        """Пустой дайджест (для отсутствующей проекции)."""
        return cls(
            revision_id='',
            revision_number=-1,
            graph_hash='0',
            metadata_hash='0',
        )

    @property
    def is_empty(self) -> bool:
        return self.revision_number < 0


@dataclass(frozen=True)
class ProjectionDigestResult:
    """Результат сравнения дайджестов."""
    is_fresh: bool
    stored_digest: ProjectionDigest
    current_digest: ProjectionDigest
    reason: str = ""
