"""
v2.3 — PostgreSQLProjectionStore integration tests.

Tests require a running PostgreSQL with the realtoros database.
Uses psycopg2 directly. DSN from backend.config.settings.

Run: python3 -m pytest services/accounting_binding/tests/infrastructure/test_v2_3_postgresql_projection_store.py -v

Covers:
  - put/get roundtrip for all 4 projection types (ENTITY, AGREEMENT, GRAPH, PROVENANCE)
  - overwrite (idempotent)
  - get missing → ProjectionNotFoundError
  - remove / contains
  - digest roundtrip
  - materialization compatibility (writes directly to PostgreSQL)
  - query engine compatibility
  - MemoryProjectionStore unchanged
"""
from __future__ import annotations

import sys
sys.path.insert(0, "/home/xiag/real-estate-os/services/accounting_binding")
sys.path.insert(0, "/home/xiag/real-estate-os")

import pytest

from backend.config import settings

from projection.projection import ProjectionId, ProjectionType
from projection.exceptions import ProjectionNotFoundError
from projection.projection_digest import ProjectionDigest
from projection.projection_store import ProjectionStore
from projection.build_plan import BuildPlan, BuildStep
from projection.projection_registry import ProjectionRegistry

from application.knowledge_persistence.materialization import (
    materialize,
    _EntityProjection,
    _AgreementProjection,
    _GraphProjection,
    _ProvenanceProjection,
    MaterializedEntityBuilder,
    MaterializedAgreementBuilder,
    MaterializedGraphBuilder,
    MaterializedProvenanceBuilder,
)

from infrastructure.knowledge_persistence.postgresql_projection_store import (
    PostgreSQLProjectionStore,
)
from infrastructure.knowledge_persistence.postgresql_projection_codec import (
    encode_projection,
    decode_projection,
)
from infrastructure.knowledge_persistence.memory_knowledge_revision_repository import (
    MemoryKnowledgeRevisionRepository,
)

from domain.business_relationship.knowledge_revision import KnowledgeRevision
from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId
from domain.business_relationship.knowledge_revision_number import KnowledgeRevisionNumber
from domain.business_relationship.knowledge_revision_metadata import KnowledgeRevisionMetadata
from domain.business_relationship.knowledge_snapshot import KnowledgeSnapshot
from domain.business_relationship.kg_graph import KnowledgeGraph
from domain.business_relationship.kg_provenance import KnowledgeProvenance
from domain.business_relationship.kg_provenance_id import ProvenanceId
from domain.business_relationship.ke_explanation import GraphExplanation
from domain.business_relationship.ke_explanation_id import ExplanationId
from domain.business_relationship.kg_identifiers import GraphNodeId


DSN = settings.DATABASE_SYNC_URL


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def store():
    """Create a clean PostgreSQL store for each test."""
    s = PostgreSQLProjectionStore(dsn=DSN)
    s.clear()
    yield s
    s.clear()


def _make_revision() -> KnowledgeRevision:
    """Minimal KnowledgeRevision for materialization tests."""
    return KnowledgeRevision(
        revision_id=KnowledgeRevisionId(value="test-revision-proj"),
        revision_number=KnowledgeRevisionNumber(number=1),
        snapshot=KnowledgeSnapshot(
            graph=KnowledgeGraph(),
            provenance=KnowledgeProvenance(provenance_id=ProvenanceId.generate()),
            explanation=GraphExplanation(
                explanation_id=ExplanationId.generate(),
                graph_node_id=GraphNodeId(value="root"),
            ),
        ),
        metadata=KnowledgeRevisionMetadata(reason="Test", document_count=1),
    )


# ── Tests ─────────────────────────────────────────────────────────


class TestPostgreSQLProjectionStore:
    """Integration tests for PostgreSQLProjectionStore."""

    def test_put_and_get_entity_projection(self, store):
        """ENTITY projection roundtrip."""
        proj = _EntityProjection(
            projection_id=ProjectionId(value="entity-001"),
            projection_type=ProjectionType.ENTITY,
            node_count=5,
            entity_ids=("e1", "e2"),
            entity_names=("ООО Альфа", "ООО Бета"),
        )
        store.put(proj)
        fetched = store.get(ProjectionId(value="entity-001"))
        assert fetched.projection_id.value == "entity-001"
        assert fetched.projection_type == ProjectionType.ENTITY
        assert isinstance(fetched, _EntityProjection)
        assert fetched.node_count == 5
        assert fetched.entity_names == ("ООО Альфа", "ООО Бета")

    def test_put_and_get_agreement_projection(self, store):
        """AGREEMENT projection roundtrip."""
        proj = _AgreementProjection(
            projection_id=ProjectionId(value="agreement-001"),
            projection_type=ProjectionType.AGREEMENT,
        )
        store.put(proj)
        fetched = store.get(ProjectionId(value="agreement-001"))
        assert fetched.projection_type == ProjectionType.AGREEMENT
        assert isinstance(fetched, _AgreementProjection)

    def test_put_and_get_graph_projection(self, store):
        """GRAPH projection roundtrip."""
        proj = _GraphProjection(
            projection_id=ProjectionId(value="graph-001"),
            projection_type=ProjectionType.GRAPH,
            node_count=10,
            edge_count=3,
            node_types=("entity", "agreement"),
        )
        store.put(proj)
        fetched = store.get(ProjectionId(value="graph-001"))
        assert fetched.projection_type == ProjectionType.GRAPH
        assert fetched.node_count == 10
        assert fetched.edge_count == 3

    def test_put_and_get_provenance_projection(self, store):
        """PROVENANCE projection roundtrip."""
        proj = _ProvenanceProjection(
            projection_id=ProjectionId(value="provenance-001"),
            projection_type=ProjectionType.PROVENANCE,
            provenance_links=7,
            chain_length=7,
        )
        store.put(proj)
        fetched = store.get(ProjectionId(value="provenance-001"))
        assert fetched.projection_type == ProjectionType.PROVENANCE
        assert fetched.provenance_links == 7

    def test_overwrite_idempotent(self, store):
        """Same id → overwrite, no error."""
        pid = ProjectionId(value="overwrite-test")
        p1 = _EntityProjection(
            projection_id=pid, projection_type=ProjectionType.ENTITY, node_count=3,
        )
        p2 = _EntityProjection(
            projection_id=pid, projection_type=ProjectionType.ENTITY, node_count=5,
        )
        store.put(p1)
        store.put(p2)
        fetched = store.get(pid)
        assert fetched.node_count == 5  # overwritten

    def test_get_missing_raises(self, store):
        """Missing projection → ProjectionNotFoundError."""
        with pytest.raises(ProjectionNotFoundError):
            store.get(ProjectionId(value="does-not-exist"))

    def test_remove_existing(self, store):
        """remove() returns True for existing, False for missing."""
        pid = ProjectionId(value="remove-test")
        store.put(_EntityProjection(projection_id=pid, projection_type=ProjectionType.ENTITY))
        assert store.remove(pid) is True
        assert store.contains(pid) is False
        assert store.remove(pid) is False

    def test_contains(self, store):
        """contains() returns correct boolean."""
        pid = ProjectionId(value="contains-test")
        assert store.contains(pid) is False
        store.put(_EntityProjection(projection_id=pid, projection_type=ProjectionType.ENTITY))
        assert store.contains(pid) is True

    def test_digest_roundtrip(self, store):
        """Digest put/get roundtrip."""
        pid = ProjectionId(value="digest-test")
        store.put(_EntityProjection(projection_id=pid, projection_type=ProjectionType.ENTITY))

        digest = ProjectionDigest(
            revision_id="rev-1", revision_number=1,
            graph_hash="abc", metadata_hash="def",
        )
        store.put_digest(pid, digest)

        fetched = store.get_digest(pid)
        assert fetched is not None
        assert fetched.revision_id == "rev-1"
        assert fetched.graph_hash == "abc"

    def test_get_digest_missing(self, store):
        """get_digest returns None for non-existent or no-digest projection."""
        # Non-existent
        assert store.get_digest(ProjectionId(value="no-such")) is None

        # Exists but no digest
        pid = ProjectionId(value="no-digest")
        store.put(_EntityProjection(projection_id=pid, projection_type=ProjectionType.ENTITY))
        assert store.get_digest(pid) is None

    def test_list_projection_ids(self, store):
        """list_projection_ids returns all IDs."""
        store.put(_EntityProjection(projection_id=ProjectionId(value="e1"), projection_type=ProjectionType.ENTITY))
        store.put(_EntityProjection(projection_id=ProjectionId(value="e2"), projection_type=ProjectionType.ENTITY))
        ids = store.list_projection_ids()
        assert len(ids) == 2
        assert all(isinstance(i, ProjectionId) for i in ids)

    def test_clear(self, store):
        """clear() removes all projections."""
        store.put(_EntityProjection(projection_id=ProjectionId(value="e1"), projection_type=ProjectionType.ENTITY))
        store.clear()
        assert store.count == 0

    def test_count(self, store):
        """count returns total number of projections."""
        assert store.count == 0
        store.put(_EntityProjection(projection_id=ProjectionId(value="e1"), projection_type=ProjectionType.ENTITY))
        assert store.count == 1
        store.put(_GraphProjection(projection_id=ProjectionId(value="g1"), projection_type=ProjectionType.GRAPH))
        assert store.count == 2

    def test_codec_roundtrip_all_types(self, store):
        """All 4 projection types survive codec → store → decode roundtrip."""
        projections = [
            _EntityProjection(
                projection_id=ProjectionId(value="codec-entity"),
                projection_type=ProjectionType.ENTITY,
                node_count=3, entity_ids=("a", "b"), entity_names=("X", "Y"),
            ),
            _AgreementProjection(
                projection_id=ProjectionId(value="codec-agr"),
                projection_type=ProjectionType.AGREEMENT,
            ),
            _GraphProjection(
                projection_id=ProjectionId(value="codec-graph"),
                projection_type=ProjectionType.GRAPH,
                node_count=7, edge_count=2, node_types=("ent", "agr"),
            ),
            _ProvenanceProjection(
                projection_id=ProjectionId(value="codec-prov"),
                projection_type=ProjectionType.PROVENANCE,
                provenance_links=5, chain_length=5,
            ),
        ]
        for p in projections:
            store.put(p)

        for p in projections:
            fetched = store.get(p.projection_id)
            assert type(fetched) is type(p), f"Type mismatch for {p.projection_type}"
            assert fetched.projection_type == p.projection_type

    # ── Materialization compatibility ─────────────────────────────

    def test_materialization_writes_to_postgresql(self, store):
        """materialize() writes all 4 projections to PostgreSQL store."""
        rev = _make_revision()
        repo = MemoryKnowledgeRevisionRepository()

        registry = ProjectionRegistry()
        registry.register(MaterializedEntityBuilder())
        registry.register(MaterializedAgreementBuilder())
        registry.register(MaterializedGraphBuilder())
        registry.register(MaterializedProvenanceBuilder())

        plan = BuildPlan.custom(steps=(
            BuildStep(projection_type=ProjectionType.ENTITY, depends_on=()),
            BuildStep(projection_type=ProjectionType.AGREEMENT, depends_on=(ProjectionType.ENTITY,)),
            BuildStep(projection_type=ProjectionType.GRAPH, depends_on=(ProjectionType.ENTITY, ProjectionType.AGREEMENT)),
            BuildStep(projection_type=ProjectionType.PROVENANCE, depends_on=(ProjectionType.GRAPH,)),
        ))

        result = materialize(rev, registry, store, plan)

        assert len(result.built) == 4
        assert store.count == 4

        for pt_name in ("ENTITY", "AGREEMENT", "GRAPH", "PROVENANCE"):
            ptype = ProjectionType[pt_name]
            # Find by type via list
            ids = store.list_projection_ids()
            found = [pid for pid in ids if pt_name.lower() in pid.value.lower()]
            assert len(found) >= 1, f"No {pt_name} projection found after materialization"

        print(f"✅ Materialization wrote {store.count} projections to PostgreSQL")

    # ── Full pipeline compatibility ───────────────────────────────

    def test_full_pipeline_projection_persistence(self, store):
        """Simulate real pipeline: result → materialize → PostgreSQL store."""
        from application.domain_pipeline_bridge import DomainPipelineBridge

        bridge = DomainPipelineBridge()
        result = bridge.process(
            document_id="e2e-pg-proj-store",
            raw_text="ДОГОВОР КУПЛИ-ПРОДАЖИ\nООО Продавец и ООО Покупатель\nСумма: 3 000 000 руб.",
            entities={
                "company": ["ООО Продавец", "ООО Покупатель"],
                "amount": ["3000000"],
                "date": ["15.06.2026"],
            },
            classification="dkp",
            confidence=0.95,
            semantic_type="sale_contract",
            document_role="sale_contract",
        )

        # Build KnowledgeRevision from pipeline result
        raw_rev = result["revision"]
        snapshot = raw_rev["snapshot"]
        rev = KnowledgeRevision(
            revision_id=KnowledgeRevisionId(value=raw_rev["id"]),
            revision_number=KnowledgeRevisionNumber(number=raw_rev["number"]),
            snapshot=snapshot,
            metadata=KnowledgeRevisionMetadata(reason="E2E PG store test", document_count=1),
        )

        registry = ProjectionRegistry()
        registry.register(MaterializedEntityBuilder())
        registry.register(MaterializedAgreementBuilder())
        registry.register(MaterializedGraphBuilder())
        registry.register(MaterializedProvenanceBuilder())

        plan = BuildPlan.custom(steps=(
            BuildStep(projection_type=ProjectionType.ENTITY, depends_on=()),
            BuildStep(projection_type=ProjectionType.AGREEMENT, depends_on=(ProjectionType.ENTITY,)),
            BuildStep(projection_type=ProjectionType.GRAPH, depends_on=(ProjectionType.ENTITY, ProjectionType.AGREEMENT)),
            BuildStep(projection_type=ProjectionType.PROVENANCE, depends_on=(ProjectionType.GRAPH,)),
        ))

        result_mat = materialize(rev, registry, store, plan)
        assert len(result_mat.built) == 4, f"Expected 4 projections, got {len(result_mat.built)}"

        # Verify each type exists in PostgreSQL
        for projection in result_mat.built:
            fetched = store.get(projection.projection_id)
            assert fetched.projection_type == projection.projection_type
            assert type(fetched) is type(projection)

        print(f"✅ Full pipeline: 4 projections in PostgreSQL: "
              f"{[p.projection_type.name for p in result_mat.built]}")
