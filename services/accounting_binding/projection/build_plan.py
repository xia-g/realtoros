"""
BuildPlan — declarative description of projection construction.

Immutable. The Coordinator receives a BuildPlan, not bool flags.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from projection.projection import ProjectionType


@dataclass(frozen=True)
class BuildStep:
    """Один шаг построения. Каждый шаг — одна проекция."""
    projection_type: ProjectionType
    depends_on: tuple[ProjectionType, ...] = ()
    label: str = ""

    def __post_init__(self) -> None:
        if not self.label:
            object.__setattr__(self, 'label', self.projection_type.name.lower())


@dataclass(frozen=True)
class BuildPlan:
    """Декларативный план построения проекций.

    Immutable. Coordinator получает BuildPlan и не принимает
    boolean-флаги.
    """
    steps: tuple[BuildStep, ...]

    @classmethod
    def full(cls) -> BuildPlan:
        """Полный план — построить все доступные проекции."""
        return cls(steps=(
            BuildStep(projection_type=ProjectionType.ENTITY, depends_on=()),
            BuildStep(projection_type=ProjectionType.AGREEMENT, depends_on=(ProjectionType.ENTITY,)),
            BuildStep(projection_type=ProjectionType.OWNERSHIP, depends_on=(ProjectionType.ENTITY,)),
            BuildStep(projection_type=ProjectionType.TIMELINE, depends_on=(ProjectionType.ENTITY, ProjectionType.AGREEMENT)),
            BuildStep(projection_type=ProjectionType.GRAPH, depends_on=(ProjectionType.ENTITY, ProjectionType.AGREEMENT)),
            BuildStep(projection_type=ProjectionType.PROVENANCE, depends_on=(ProjectionType.GRAPH,)),
            BuildStep(projection_type=ProjectionType.RISK, depends_on=(ProjectionType.ENTITY, ProjectionType.OWNERSHIP)),
        ))

    @classmethod
    def single(cls, pt: ProjectionType) -> BuildPlan:
        """План для одной проекции."""
        return cls(steps=(BuildStep(projection_type=pt),))

    @classmethod
    def custom(cls, steps: Sequence[BuildStep]) -> BuildPlan:
        """Пользовательский план."""
        return cls(steps=tuple(steps))

    @property
    def projection_types(self) -> tuple[ProjectionType, ...]:
        return tuple(s.projection_type for s in self.steps)

    def depends_on(self, pt: ProjectionType) -> tuple[ProjectionType, ...]:
        """Возвращает зависимости для заданного типа."""
        for step in self.steps:
            if step.projection_type == pt:
                return step.depends_on
        return ()
