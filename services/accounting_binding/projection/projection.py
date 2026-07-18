"""
Projection — immutable Read Model base.

Projection is NOT a Domain Object, NOT an Entity, NOT an Aggregate,
NOT a Repository. It is exclusively a materialised view of Domain.

No business logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol


class ProjectionType(Enum):
    """Типы проекций. Каждый тип соответствует одному материализованному представлению."""
    ENTITY = auto()
    OWNERSHIP = auto()
    TIMELINE = auto()
    GRAPH = auto()
    RISK = auto()
    AGREEMENT = auto()
    PROVENANCE = auto()


@dataclass(frozen=True)
class ProjectionId:
    """Immutable projection identifier."""
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("ProjectionId must not be empty")


class Projection(Protocol):
    """Базовый протокол для всех проекций.

    Каждая Projection:
    - immutable (frozen dataclass)
    - содержит projection_id и projection_type
    - не содержит бизнес-логики
    - является материализованным представлением Domain
    """

    projection_id: ProjectionId
    projection_type: ProjectionType
