"""
ProjectionBuilder Protocol — Domain → Projection transformation.

Builder is the ONLY component in the Projection layer allowed to read Domain.
Returns only Projection. No Store knowledge. No Query knowledge.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Any, Optional

from projection.projection import Projection, ProjectionId, ProjectionType


class ProjectionBuilder(Protocol):
    """Протокол Builder.

    Builder является единственным компонентом слоя,
    которому разрешено читать Domain.

    Наружу возвращает только Projection.
    Не зависит от Store. Не знает Query.
    """

    @property
    def projection_type(self) -> ProjectionType:
        """Тип проекции, которую строит этот Builder."""
        ...

    def build(self, domain_state: object, projection_id: ProjectionId) -> Projection:
        """Build projection from Domain state.

        Args:
            domain_state: корневой Domain объект (KnowledgeRevision, KnowledgeGraph etc.)
            projection_id: идентификатор для создаваемой проекции

        Returns:
            Immutable Projection
        """
        ...

    def can_build(self, domain_state: object) -> bool:
        """Проверяет, возможно ли построить проекцию из данного состояния.

        Позволяет Coordinator пропустить шаги, для которых нет данных.
        """
        ...
