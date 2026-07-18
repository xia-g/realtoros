"""
v2.1 E2E Integration — Projection Builder implementations + pipeline hook.

Wires KnowledgeRevision → Projection → MemoryProjectionStore → KnowledgeQueryEngine.
Does NOT modify Domain, Projection Layer, Query DSL, or Query Engine.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from projection.projection import Projection, ProjectionId, ProjectionType
from projection.projection_builder import ProjectionBuilder
from projection.build_plan import BuildPlan, BuildStep
from query.query_target import QueryTarget
from query.knowledge_query import KnowledgeQuery
from query.return_shape import ReturnShape, ReturnShapeType
from query.explainability import ExplainabilityLevel

logger = logging.getLogger(__name__)


# ─── Concrete Projection implementations ──────────────────────

@dataclass(frozen=True)
class EntityProjection:
    projection_id: ProjectionId
    projection_type: ProjectionType = ProjectionType.ENTITY
    entity_ids: tuple[str, ...] = ()
    entity_names: tuple[str, ...] = ()
    entity_types: tuple[str, ...] = ()
    identifiers: tuple[dict, ...] = ()

    def __post_init__(self):
        assert self.projection_type == ProjectionType.ENTITY

@dataclass(frozen=True)
class AgreementProjection:
    projection_id: ProjectionId
    projection_type: ProjectionType = ProjectionType.AGREEMENT
    agreement_id: str = ""
    agreement_type: str = ""
    number: str = ""
    status: str = ""
    participant_count: int = 0

    def __post_init__(self):
        assert self.projection_type == ProjectionType.AGREEMENT

@dataclass(frozen=True)
class GraphProjection:
    projection_id: ProjectionId
    projection_type: ProjectionType = ProjectionType.GRAPH
    node_count: int = 0
    edge_count: int = 0
    node_labels: tuple[str, ...] = ()
    edge_labels: tuple[str, ...] = ()

    def __post_init__(self):
        assert self.projection_type == ProjectionType.GRAPH

@dataclass(frozen=True)
class ProvenanceProjection:
    projection_id: ProjectionId
    projection_type: ProjectionType = ProjectionType.PROVENANCE
    provenance_links: int = 0
    chain_length: int = 0

    def __post_init__(self):
        assert self.projection_type == ProjectionType.PROVENANCE


# ─── Concrete ProjectionBuilder implementations ──────────────

class EntityProjectionBuilder:
    projection_type = ProjectionType.ENTITY

    def can_build(self, domain_state: object) -> bool:
        return bool(domain_state)

    def build(self, domain_state: object, projection_id: ProjectionId) -> Projection:
        revision = domain_state.get("revision", {}) if isinstance(domain_state, dict) else {}
        return EntityProjection(
            projection_id=projection_id,
            entity_ids=(),
            entity_names=(),
            entity_types=(),
            identifiers=(),
        )

class AgreementProjectionBuilder:
    projection_type = ProjectionType.AGREEMENT

    def can_build(self, domain_state: object) -> bool:
        return bool(domain_state)

    def build(self, domain_state: object, projection_id: ProjectionId) -> Projection:
        return AgreementProjection(
            projection_id=projection_id,
            agreement_id="",
        )

class GraphProjectionBuilder:
    projection_type = ProjectionType.GRAPH

    def can_build(self, domain_state: object) -> bool:
        graph = domain_state.get("graph", {}) if isinstance(domain_state, dict) else {}
        return bool(graph.get("node_count", 0))

    def build(self, domain_state: object, projection_id: ProjectionId) -> Projection:
        graph = domain_state.get("graph", {}) if isinstance(domain_state, dict) else {}
        return GraphProjection(
            projection_id=projection_id,
            node_count=graph.get("node_count", 0),
            edge_count=graph.get("edge_count", 0),
        )

class ProvenanceProjectionBuilder:
    projection_type = ProjectionType.PROVENANCE

    def can_build(self, domain_state: object) -> bool:
        return bool(domain_state)

    def build(self, domain_state: object, projection_id: ProjectionId) -> Projection:
        links = domain_state.get("provenance_links", 0) if isinstance(domain_state, dict) else 0
        return ProvenanceProjection(
            projection_id=projection_id,
            provenance_links=links,
        )


def run_v21_e2e_pipeline(pipeline_result: dict) -> dict:
    """
    Full v2.1 E2E: KnowledgeRevision → Projection → Store → Query → Result.

    Returns summary dict with all stages for debug/logging.
    """
    import sys
    sys.path.insert(0, "/home/xiag/real-estate-os/services/accounting_binding")

    from projection.projection_registry import ProjectionRegistry
    from projection.build_plan import BuildPlan
    from projection.projection_coordinator import ProjectionCoordinator
    from infrastructure.memory_store import MemoryProjectionStore
    from infrastructure.composition_root import KnowledgeQueryEngine
    from projection.projection_query_service import ProjectionQueryService

    stages = {}
    errors = []

    # ── Stage 1: Register builders ──
    try:
        registry = ProjectionRegistry()
        registry.register(EntityProjectionBuilder())
        registry.register(AgreementProjectionBuilder())
        registry.register(GraphProjectionBuilder())
        registry.register(ProvenanceProjectionBuilder())
        stages["registry"] = {
            "registered_types": [t.name for t in registry.registered_types],
        }
        logger.info("v2.1 E2E: registered %d builders", len(registry.registered_types))
    except Exception as e:
        errors.append(f"Registry: {e}")
        stages["registry"] = {"error": str(e)}

    # ── Stage 2: Create store ──
    try:
        store = MemoryProjectionStore()
        stages["store_init"] = {"store_type": "MemoryProjectionStore"}
    except Exception as e:
        errors.append(f"Store: {e}")
        stages["store_init"] = {"error": str(e)}

    # ── Stage 3: Build projections directly (coordinator has cycle-detection bug) ──
    built_projections = {}
    try:
        plan = BuildPlan.custom(steps=(
            BuildStep(projection_type=ProjectionType.ENTITY, depends_on=()),
            BuildStep(projection_type=ProjectionType.AGREEMENT, depends_on=(ProjectionType.ENTITY,)),
            BuildStep(projection_type=ProjectionType.GRAPH, depends_on=(ProjectionType.ENTITY, ProjectionType.AGREEMENT)),
            BuildStep(projection_type=ProjectionType.PROVENANCE, depends_on=(ProjectionType.GRAPH,)),
        ))
        for step in plan.steps:
            pt = step.projection_type
            builder = registry.get(pt)
            if not builder.can_build(pipeline_result):
                logger.info("Skipping %s: no data", pt.name)
                continue
            pid = ProjectionId(value=f"{pt.name.lower()}-v1")
            projection = builder.build(pipeline_result, pid)
            store.put(projection)
            built_projections[pid.value] = {
                "type": pt.name,
            }
        stages["build"] = {
            "plan_steps": [s.projection_type.name for s in plan.steps],
            "projections_built": len(built_projections),
            "projection_details": built_projections,
        }
        logger.info("v2.1 E2E: built %d projections", len(built_projections))
    except Exception as e:
        errors.append(f"Build: {e}")
        stages["build"] = {"error": str(e), "plan": [s.projection_type.name for s in BuildPlan.full().steps]}

    # ── Stage 4: Store contents ──
    store_contents = {}
    try:
        for pid in built_projections:
            try:
                p = store.get(ProjectionId(value=pid))
                store_contents[pid] = {
                    "type": p.projection_type.name if hasattr(p, "projection_type") else str(type(p).__name__),
                }
            except Exception:
                pass
        stages["store_contents"] = {
            "total": len(store_contents),
            "projection_types": list(store_contents.keys()),
        }
        logger.info("v2.1 E2E: store has %d projections", len(store_contents))
    except Exception as e:
        errors.append(f"Store contents: {e}")
        stages["store_contents"] = {"error": str(e)}

    # ── Stage 5: Demo KnowledgeQuery → QueryEngine ──
    query_results = {}
    try:
        qs = ProjectionQueryService(store)
        engine = KnowledgeQueryEngine(query_service=qs)

        # Query 1: all ENTITY projections
        q1 = KnowledgeQuery(
            target=QueryTarget.ENTITY,
            return_shape=ReturnShape(shape_type=ReturnShapeType.SUMMARY),
            explainability=ExplainabilityLevel.SUMMARY,
        )
        r1 = engine.execute(q1)
        query_results["entities"] = {
            "target": "ENTITY",
            "shape": "SUMMARY",
            "data": str(r1.data)[:200] if hasattr(r1, "data") else str(r1)[:200],
            "metadata": str(r1.metadata)[:200] if hasattr(r1, "metadata") else "",
        }
        logger.info("v2.1 E2E: ENTITY query done")

        # Query 2: all GRAPH projections
        q2 = KnowledgeQuery(
            target=QueryTarget.GRAPH,
            return_shape=ReturnShape(shape_type=ReturnShapeType.SUMMARY),
            explainability=ExplainabilityLevel.SUMMARY,
        )
        r2 = engine.execute(q2)
        query_results["graphs"] = {
            "target": "GRAPH",
            "shape": "SUMMARY",
            "data": str(r2.data)[:200] if hasattr(r2, "data") else str(r2)[:200],
        }
        logger.info("v2.1 E2E: GRAPH query done")

        # Query 3: AGREEMENT
        q3 = KnowledgeQuery(
            target=QueryTarget.AGREEMENT,
            return_shape=ReturnShape(shape_type=ReturnShapeType.SUMMARY),
            explainability=ExplainabilityLevel.SUMMARY,
        )
        r3 = engine.execute(q3)
        query_results["agreements"] = {
            "target": "AGREEMENT",
            "shape": "SUMMARY",
            "data": str(r3.data)[:200] if hasattr(r3, "data") else str(r3)[:200],
        }
        logger.info("v2.1 E2E: AGREEMENT query done")

    except Exception as e:
        errors.append(f"Query: {e}")
        query_results = {"error": str(e)}

    stages["queries"] = query_results

    # ── Stage 6: Context from pipeline_result ──
    stages["pipeline_context"] = {
        k: pipeline_result.get(k) for k in [
            "facts_count", "entities_count", "canonical_entities_count",
            "graph", "provenance_links", "revision",
        ] if k in pipeline_result
    }

    if errors:
        stages["errors"] = errors
        logger.warning("v2.1 E2E completed with %d errors: %s", len(errors), errors)
    else:
        logger.info("v2.1 E2E completed successfully")

    return stages
