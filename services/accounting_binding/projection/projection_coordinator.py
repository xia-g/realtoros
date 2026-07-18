"""
ProjectionCoordinator — single orchestrator of the Projection layer.

Receives BuildPlan, finds Builders, coordinates construction,
stores results via Store Protocol.

NO build logic. NO Domain details.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from projection.projection import Projection, ProjectionId, ProjectionType
from projection.build_plan import BuildPlan, BuildStep
from projection.projection_registry import ProjectionRegistry
from projection.projection_store import ProjectionStore
from projection.projection_digest import ProjectionDigest
from projection.exceptions import (
    ProjectionBuildError,
    ProjectionBuilderNotFoundError,
    BuildPlanError,
)


@dataclass(frozen=True)
class CoordinatorResult:
    """Результат работы Coordinator."""
    built: tuple[Projection, ...]
    skipped: tuple[str, ...]
    errors: tuple[str, ...]


class ProjectionCoordinator:
    """Оркестратор слоя Projection.

    Coordinator:
    - получает BuildPlan;
    - находит Builder через Registry;
    - запускает построение;
    - сохраняет Projection в Store.

    Coordinator не содержит логики построения Projection.
    Coordinator не знает деталей Domain.
    """

    def __init__(
        self,
        registry: ProjectionRegistry,
        store: ProjectionStore,
    ) -> None:
        self._registry = registry
        self._store = store

    def execute(
        self,
        plan: BuildPlan,
        domain_state: object,
    ) -> CoordinatorResult:
        """Execute a BuildPlan.

        Args:
            plan: декларативный план построения
            domain_state: корневой Domain объект (KnowledgeRevision)

        Returns:
            CoordinatorResult со списком построенных проекций
        """
        built: list[Projection] = []
        skipped: list[str] = []
        errors: list[str] = []
        built_types: set[ProjectionType] = set()

        # Build dependency map
        dep_map = self._resolve_dependencies(plan)

        for step in plan.steps:
            pt = step.projection_type

            # Check dependencies
            missing_deps = [
                d.name for d in step.depends_on
                if d not in built_types
            ]
            if missing_deps:
                errors.append(
                    f"Cannot build {pt.name}: missing dependencies {missing_deps}"
                )
                continue

            # Find builder
            try:
                builder = self._registry.get(pt)
            except ProjectionBuilderNotFoundError as e:
                errors.append(str(e))
                continue

            # Check if buildable
            if not builder.can_build(domain_state):
                skipped.append(f"{pt.name}: no data available")
                continue

            # Build
            try:
                projection_id = ProjectionId(value=f"{pt.name.lower()}-v1")
                projection = builder.build(domain_state, projection_id)
            except Exception as e:
                errors.append(f"{pt.name}: build failed: {e}")
                continue

            # Store
            try:
                self._store.put(projection)
            except Exception as e:
                errors.append(f"{pt.name}: store failed: {e}")
                continue

            built.append(projection)
            built_types.add(pt)

        return CoordinatorResult(
            built=tuple(built),
            skipped=tuple(skipped),
            errors=tuple(errors),
        )

    def _resolve_dependencies(self, plan: BuildPlan) -> dict[ProjectionType, tuple[ProjectionType, ...]]:
        """Validate and resolve dependency map.

        Raises BuildPlanError if circular dependencies detected.
        """
        dep_map: dict[ProjectionType, tuple[ProjectionType, ...]] = {}
        for step in plan.steps:
            dep_map[step.projection_type] = step.depends_on

        # Simple cycle detection
        for pt in dep_map:
            visited = {pt}
            queue = list(dep_map[pt])
            while queue:
                current = queue.pop(0)
                if current in visited:
                    raise BuildPlanError(f"Circular dependency detected for {pt.name}")
                visited.add(current)
                queue.extend(dep_map.get(current, ()))

        return dep_map
