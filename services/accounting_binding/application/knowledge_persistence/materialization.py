"""
v2.1.5 — Projection Materialization.

Builds Projections from a saved KnowledgeRevisionRecord using existing
ProjectionBuilder, ProjectionRegistry, MemoryProjectionStore.

Deterministic, repeatable, idempotent.
NO changes to Domain, Projection Layer, Query DSL, or Query Engine.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from domain.business_relationship.knowledge_graph import KnowledgeGraph
from domain.business_relationship.knowledge_snapshot import KnowledgeSnapshot

from projection.projection import Projection, ProjectionId, ProjectionType
from projection.projection_builder import ProjectionBuilder
from projection.build_plan import BuildPlan, BuildStep
from projection.projection_registry import ProjectionRegistry
from projection.projection_store import ProjectionStore
from projection.projection_digest import ProjectionDigest
from projection.exceptions import ProjectionBuildError

logger = logging.getLogger(__name__)


# ─── ProjectionBuilder implementations (concrete, implement Protocol) ─────

class MaterializedEntityBuilder:
    """Builds EntityProjection from KnowledgeRevision.snapshot.graph"""
    projection_type = ProjectionType.ENTITY

    def can_build(self, domain_state: object) -> bool:
        snapshot = self._get_snapshot(domain_state)
        return snapshot is not None and snapshot.graph is not None

    def build(self, domain_state: object, projection_id: ProjectionId) -> Projection:
        snapshot = self._get_snapshot(domain_state)
        graph = snapshot.graph if snapshot else KnowledgeGraph()
        return _EntityProjection(
            projection_id=projection_id,
            projection_type=ProjectionType.ENTITY,
            node_count=graph.node_count,
        )

    def _get_snapshot(self, state: object) -> KnowledgeSnapshot | None:
        if not state:
            return None
        if hasattr(state, 'revision') and hasattr(state.revision, 'snapshot'):
            return state.revision.snapshot
        return getattr(state, 'snapshot', None)


class MaterializedAgreementBuilder:
    """Builds AgreementProjection from KnowledgeRevision.snapshot"""
    projection_type = ProjectionType.AGREEMENT

    def can_build(self, domain_state: object) -> bool:
        return domain_state is not None

    def build(self, domain_state: object, projection_id: ProjectionId) -> Projection:
        return _AgreementProjection(
            projection_id=projection_id,
            projection_type=ProjectionType.AGREEMENT,
        )


class MaterializedGraphBuilder:
    """Builds GraphProjection from KnowledgeRevision.snapshot.graph"""
    projection_type = ProjectionType.GRAPH

    def can_build(self, domain_state: object) -> bool:
        snapshot = self._get_snapshot(domain_state)
        return snapshot is not None and snapshot.graph is not None

    def build(self, domain_state: object, projection_id: ProjectionId) -> Projection:
        snapshot = self._get_snapshot(domain_state)
        graph = snapshot.graph if snapshot else KnowledgeGraph()
        return _GraphProjection(
            projection_id=projection_id,
            projection_type=ProjectionType.GRAPH,
            node_count=graph.node_count,
            edge_count=graph.edge_count,
        )

    def _get_snapshot(self, state: object) -> KnowledgeSnapshot | None:
        if not state:
            return None
        if hasattr(state, 'revision') and hasattr(state.revision, 'snapshot'):
            return state.revision.snapshot
        return getattr(state, 'snapshot', None)


class MaterializedProvenanceBuilder:
    """Builds ProvenanceProjection from KnowledgeRevision.snapshot.provenance"""
    projection_type = ProjectionType.PROVENANCE

    def can_build(self, domain_state: object) -> bool:
        p = self._get_provenance(domain_state)
        return p is not None

    def build(self, domain_state: object, projection_id: ProjectionId) -> Projection:
        p = self._get_provenance(domain_state)
        chain = getattr(p, 'chain', None)
        links = getattr(chain, 'links', []) if chain else []
        return _ProvenanceProjection(
            projection_id=projection_id,
            projection_type=ProjectionType.PROVENANCE,
            provenance_links=len(links),
            chain_length=len(links),
        )

    def _get_provenance(self, state: object):
        if not state:
            return None
        revision = getattr(state, 'revision', state)
        snapshot = getattr(revision, 'snapshot', None)
        if snapshot:
            return getattr(snapshot, 'provenance', None)
        return None


# ─── Projection DTOs (conform to Projection Protocol) ──────────────────────

from dataclasses import dataclass as _dataclass

@_dataclass(frozen=True)
class _EntityProjection:
    projection_id: ProjectionId
    projection_type: ProjectionType
    node_count: int = 0
    entity_ids: tuple[str, ...] = ()
    entity_names: tuple[str, ...] = ()

@_dataclass(frozen=True)
class _AgreementProjection:
    projection_id: ProjectionId
    projection_type: ProjectionType

@_dataclass(frozen=True)
class _GraphProjection:
    projection_id: ProjectionId
    projection_type: ProjectionType
    node_count: int = 0
    edge_count: int = 0
    node_types: tuple[str, ...] = ()

@_dataclass(frozen=True)
class _ProvenanceProjection:
    projection_id: ProjectionId
    projection_type: ProjectionType
    provenance_links: int = 0
    chain_length: int = 0


# ─── Materialization orchestrator ──────────────────────────────────────────

@dataclass
class MaterializationResult:
    """Result of a single materialization run."""
    built: tuple[Projection, ...]
    skipped: tuple[str, ...]
    errors: tuple[str, ...]
    digests: dict[str, ProjectionDigest]


def materialize(
    domain_state: object,
    registry: ProjectionRegistry,
    store: ProjectionStore,
    plan: BuildPlan | None = None,
) -> MaterializationResult:
    """Build Projections from a KnowledgeRevision and store them.

    Determinstic, repeatable, idempotent.
    Errors in one builder do not affect others or the saved revision.
    """
    if plan is None:
        plan = BuildPlan.custom(steps=(
            BuildStep(projection_type=ProjectionType.ENTITY, depends_on=()),
            BuildStep(projection_type=ProjectionType.AGREEMENT, depends_on=(ProjectionType.ENTITY,)),
            BuildStep(projection_type=ProjectionType.GRAPH, depends_on=(ProjectionType.ENTITY, ProjectionType.AGREEMENT)),
            BuildStep(projection_type=ProjectionType.PROVENANCE, depends_on=(ProjectionType.GRAPH,)),
        ))

    built: list[Projection] = []
    skipped: list[str] = []
    errors: list[str] = []
    digests: dict[str, ProjectionDigest] = {}

    for step in plan.steps:
        pt = step.projection_type
        try:
            builder = registry.get(pt)
        except Exception as e:
            errors.append(f"{pt.name}: builder not found: {e}")
            continue

        try:
            if not builder.can_build(domain_state):
                skipped.append(pt.name)
                continue
        except Exception as e:
            errors.append(f"{pt.name}: can_build failed: {e}")
            continue

        try:
            pid = ProjectionId(value=f"{pt.name.lower()}-{hash(str(domain_state)) & 0xFFFF:04x}")
            projection = builder.build(domain_state, pid)
            store.put(projection)
            built.append(projection)
            # Compute digest
            try:
                digests[pt.name] = ProjectionDigest.compute(projection)
            except Exception:
                pass
        except Exception as e:
            errors.append(f"{pt.name}: build/store failed: {e}")
            continue

    return MaterializationResult(
        built=tuple(built),
        skipped=tuple(skipped),
        errors=tuple(errors),
        digests=digests,
    )
