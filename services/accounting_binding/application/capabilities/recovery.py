"""
Knowledge Recovery v1 — models and stateless repair logic.

Pure functions over KnowledgeSnapshot. Creates new KnowledgeRevision.
No Platform changes — uses existing Repository.save().
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from domain.business_relationship.knowledge_revision import KnowledgeRevision
from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId
from domain.business_relationship.knowledge_revision_number import KnowledgeRevisionNumber
from domain.business_relationship.knowledge_revision_metadata import KnowledgeRevisionMetadata
from domain.business_relationship.knowledge_snapshot import KnowledgeSnapshot
from domain.business_relationship.kg_graph import KnowledgeGraph
from domain.business_relationship.kg_node import GraphNode
from domain.business_relationship.kg_edge import GraphEdge
from domain.business_relationship.kg_enums import GraphNodeType

from application.capabilities.consistency_check import (
    check_snapshot_consistency,
    ConsistencyViolation,
)
from application.capabilities.governance import GovernanceDecision


# ─── Models ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class RepairAction:
    action_type: str          # "remove_broken_edge" | "remove_duplicate"
    violation_type: str
    target_id: str
    description: str


@dataclass(frozen=True)
class RecoveryPlan:
    source_revision_id: str
    governance_status: str    # "APPROVED" | "REJECTED" | "CHECK_REQUIRED"
    actions: tuple[RepairAction, ...]
    violations_count: int = 0
    actionable_count: int = 0


@dataclass(frozen=True)
class RecoveryResult:
    source_revision_id: str
    recovery_revision_id: str = ""
    actions_performed: int = 0
    success: bool = False
    message: str = ""


# ─── Repair functions ────────────────────────────────────────────


def _repair_snapshot(
    snapshot: KnowledgeSnapshot,
    violations: tuple[ConsistencyViolation, ...],
) -> tuple[KnowledgeSnapshot, tuple[RepairAction, ...]]:
    """Create a repaired copy of a KnowledgeSnapshot.

    Returns:
        Tuple of (repaired_snapshot, actions_taken)
    """
    graph = snapshot.graph
    nodes = list(graph.nodes)
    edges = list(graph.edges)

    # Collect node_ids for validation
    node_ids = {n.node_id.value for n in nodes}
    actions: list[RepairAction] = []

    # 1. Remove broken edges (source or target not in node_ids)
    valid_edges: list[GraphEdge] = []
    for edge in edges:
        src_ok = edge.source_node.value in node_ids
        tgt_ok = edge.target_node.value in node_ids
        if src_ok and tgt_ok:
            valid_edges.append(edge)
        else:
            actions.append(RepairAction(
                action_type="remove_broken_edge",
                violation_type="broken_edge",
                target_id=edge.edge_id.value,
                description=f"Removed edge referencing non-existent node",
            ))

    # 2. Remove duplicate nodes (same node_type + domain_id, keep first)
    seen_logical: dict[tuple[str, str], int] = {}
    valid_nodes: list[GraphNode] = []
    for node in nodes:
        nt = node.node_type.value if isinstance(node.node_type, GraphNodeType) else str(node.node_type)
        key = (nt, node.domain_id)
        if key in seen_logical:
            actions.append(RepairAction(
                action_type="remove_duplicate",
                violation_type="duplicate_node",
                target_id=node.node_id.value,
                description=f"Removed duplicate node ({nt}, {node.domain_id})",
            ))
            continue
        seen_logical[key] = 1
        valid_nodes.append(node)

    # 3. Rebuild graph + snapshot
    repaired_graph = KnowledgeGraph(
        nodes=tuple(valid_nodes),
        edges=tuple(valid_edges),
        metadata=graph.metadata,
    )

    repaired_snapshot = KnowledgeSnapshot(
        graph=repaired_graph,
        provenance=snapshot.provenance,
        explanation=snapshot.explanation,
    )

    return repaired_snapshot, tuple(actions)


def _next_revision_number(record: Any) -> int:
    """Determine the next revision number for a repair revision."""
    return record.revision.revision_number.number + 1


# ─── Plan and Execute ─────────────────────────────────────────────


def build_recovery_plan(
    source_revision_id: str,
    snapshot: KnowledgeSnapshot,
    governance_decision: GovernanceDecision | None = None,
) -> RecoveryPlan:
    """Build a recovery plan (dry-run, no changes).

    Args:
        source_revision_id: The revision to repair.
        snapshot: The KnowledgeSnapshot to analyze.
        governance_decision: Optional governance check result.
    """
    consistency = check_snapshot_consistency(snapshot)

    if not consistency.violations:
        return RecoveryPlan(
            source_revision_id=source_revision_id,
            governance_status="APPROVED",
            actions=(),
            violations_count=0,
            actionable_count=0,
        )

    _, actions = _repair_snapshot(snapshot, consistency.violations)

    gov_status = "CHECK_REQUIRED"
    if governance_decision:
        gov_status = governance_decision.decision  # APPROVED | REJECTED

    return RecoveryPlan(
        source_revision_id=source_revision_id,
        governance_status=gov_status,
        actions=actions,
        violations_count=len(consistency.violations),
        actionable_count=len(actions),
    )


def execute_recovery(
    source_record: Any,
    governance_decision: GovernanceDecision,
) -> RecoveryResult:
    """Execute a recovery plan — creates a new KnowledgeRevision.

    Requires governance_decision.decision == "APPROVED".
    Original revision is never modified.
    """
    if governance_decision.decision != "APPROVED":
        return RecoveryResult(
            source_revision_id=source_record.revision.revision_id.value,
            success=False,
            message=f"Recovery blocked: governance decision is {governance_decision.decision}",
        )

    source_rev = source_record.revision
    snapshot = source_rev.snapshot
    source_id = source_rev.revision_id.value

    # Build plan and repair
    consistency = check_snapshot_consistency(snapshot)
    if not consistency.violations:
        return RecoveryResult(
            source_revision_id=source_id,
            success=False,
            message="No violations found — nothing to repair",
        )

    repaired_snapshot, actions = _repair_snapshot(snapshot, consistency.violations)

    if not actions:
        return RecoveryResult(
            source_revision_id=source_id,
            success=False,
            message="No actionable violations (all warnings, no errors)",
        )

    # Create new revision
    new_rev_id = f"recovery-{source_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    new_number = _next_revision_number(source_record)

    action_summary = "; ".join(
        f"{a.action_type}: {a.target_id}" for a in actions[:5]
    )

    new_meta = KnowledgeRevisionMetadata(
        created_at=datetime.now(timezone.utc),
        created_by="system:recovery",
        reason=f"Recovery from {source_id}: {action_summary}",
        document_count=1,
    )

    new_revision = KnowledgeRevision(
        revision_id=KnowledgeRevisionId(value=new_rev_id),
        revision_number=KnowledgeRevisionNumber(number=new_number),
        snapshot=repaired_snapshot,
        metadata=new_meta,
    )

    return RecoveryResult(
        source_revision_id=source_id,
        recovery_revision_id=new_rev_id,
        actions_performed=len(actions),
        success=True,
        message=f"Recovery complete: {len(actions)} actions, new revision {new_rev_id}",
    )
