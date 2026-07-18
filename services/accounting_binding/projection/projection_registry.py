"""
ProjectionRegistry — maps ProjectionType → ProjectionBuilder.

Fully declarative. Coordinator never knows specific Builders.
"""
from __future__ import annotations

from typing import Any, Optional

from projection.projection import ProjectionType
from projection.projection_builder import ProjectionBuilder
from projection.exceptions import ProjectionBuilderNotFoundError


class ProjectionRegistry:
    """Реестр, отображающий ProjectionType → ProjectionBuilder.

    Coordinator никогда не знает конкретные Builder.
    Регистрация полностью декларативная.
    """

    def __init__(self) -> None:
        self._builders: dict[ProjectionType, ProjectionBuilder] = {}

    def register(self, builder: ProjectionBuilder) -> None:
        """Register a builder."""
        self._builders[builder.projection_type] = builder

    def get(self, pt: ProjectionType) -> ProjectionBuilder:
        """Get builder by projection type.

        Raises ProjectionBuilderNotFoundError if not registered.
        """
        builder = self._builders.get(pt)
        if builder is None:
            raise ProjectionBuilderNotFoundError(
                f"No builder registered for {pt.name}"
            )
        return builder

    def has(self, pt: ProjectionType) -> bool:
        """Check if builder is registered."""
        return pt in self._builders

    @property
    def registered_types(self) -> tuple[ProjectionType, ...]:
        return tuple(self._builders.keys())
