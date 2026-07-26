"""
Knowledge Trust State v1 — models and stateless evaluation.

Pure functions over KnowledgeSnapshot + ConsistencyCheck.
No Platform changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone

from domain.business_relationship.knowledge_snapshot import KnowledgeSnapshot
from domain.business_relationship.kg_enums import GraphNodeType

from application.capabilities.consistency_check import (
    check_snapshot_consistency,
    ConsistencyViolation,
)


# ─── Models ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class TrustViolationSummary:
    type: str
    severity: str
    count: int


@dataclass(frozen=True)
class TrustState:
    """Current trust state for a KnowledgeRevision.

    Status:
      VALID    — no structural violations
      WARNING  — non-critical violations (orphan, missing provenance)
      INVALID  — critical structural violations (broken edge, duplicate)
      UNKNOWN  — insufficient data (empty snapshot)
    """
    status: str
    reasons: tuple[str, ...] = ()
    violations: tuple[TrustViolationSummary, ...] = ()
    structural_errors: int = 0
    structural_warnings: int = 0
    node_count: int = 0
    edge_count: int = 0
    provenance_coverage: float = 0.0


@dataclass(frozen=True)
class TrustEvaluation:
    """Complete trust evaluation result."""
    revision_id: str = ""
    trust: TrustState | None = None
    evaluated_at: str = ""
    has_provenance: bool = False
    has_explanation: bool = False


# ─── Status determination ────────────────────────────────────────


CRITICAL_TYPES = {"broken_edge", "duplicate_node", "invalid_relation"}
WARNING_TYPES = {"orphan_node", "missing_provenance", "self_reference"}


def _determine_trust_status(
    is_consistent: bool,
    violations: tuple[ConsistencyViolation, ...],
    node_count: int,
) -> tuple[str, list[str]]:
    """Determine trust status and reasons based on violations.

    Rules:
      - Empty snapshot (no nodes) → UNKNOWN
      - Any critical violation → INVALID
      - Non-critical violations only → WARNING
      - No violations → VALID
    """
    reasons: list[str] = []

    if node_count == 0:
        return ("UNKNOWN", reasons)

    critical: list[str] = []
    warnings_list: list[str] = []

    for v in violations:
        if v.violation_type in CRITICAL_TYPES:
            critical.append(v.message)
        elif v.violation_type in WARNING_TYPES:
            warnings_list.append(v.message)

    if critical:
        reasons.extend(critical[:3])  # top 3 reasons
        return ("INVALID", reasons)

    if warnings_list:
        reasons.extend(warnings_list[:3])
        return ("WARNING", reasons)

    return ("VALID", reasons)


def _compute_provenance_coverage(
    node_count: int,
    snapshot: KnowledgeSnapshot,
) -> float:
    """Fraction of nodes with at least one provenance link."""
    if node_count == 0:
        return 0.0
    linked: set[str] = set()
    if snapshot.provenance:
        for link in snapshot.provenance.chain.links:
            linked.add(link.graph_node_id.value)
    # Map node_ids to count how many have provenance
    total_with_prov = 0
    for node in snapshot.graph.nodes:
        if node.node_id.value in linked:
            total_with_prov += 1
    return round(total_with_prov / node_count, 2)


def _aggregate_violations(
    violations: tuple[ConsistencyViolation, ...],
) -> tuple[TrustViolationSummary, ...]:
    """Group violations by type and severity."""
    counts: dict[str, dict[str, int]] = {}
    for v in violations:
        if v.violation_type not in counts:
            counts[v.violation_type] = {"error": 0, "warning": 0}
        counts[v.violation_type][v.severity] = (
            counts[v.violation_type].get(v.severity, 0) + 1
        )

    result: list[TrustViolationSummary] = []
    for vtype, sevs in sorted(counts.items()):
        # Highest severity for this type
        sev = "error" if sevs.get("error", 0) > 0 else "warning"
        count = sevs.get("error", 0) + sevs.get("warning", 0)
        result.append(TrustViolationSummary(type=vtype, severity=sev, count=count))
    return tuple(result)


# ─── Main evaluation ─────────────────────────────────────────────


def evaluate_trust(
    snapshot: KnowledgeSnapshot,
    revision_id: str = "",
) -> TrustEvaluation:
    """Evaluate trust state for a KnowledgeSnapshot.

    Pure function. Snapshot is not modified.
    Deterministic: same snapshot → same trust state.
    """
    node_count = snapshot.graph.node_count
    edge_count = snapshot.graph.edge_count

    # Run Consistency Check (stateless)
    consistency = check_snapshot_consistency(snapshot)

    status, reasons = _determine_trust_status(
        consistency.is_consistent,
        consistency.violations,
        node_count,
    )

    prov_coverage = _compute_provenance_coverage(node_count, snapshot)
    violation_summary = _aggregate_violations(consistency.violations)

    trust = TrustState(
        status=status,
        reasons=tuple(reasons),
        violations=violation_summary,
        structural_errors=consistency.errors,
        structural_warnings=consistency.warnings,
        node_count=node_count,
        edge_count=edge_count,
        provenance_coverage=prov_coverage,
    )

    has_provenance = (
        snapshot.provenance is not None
        and len(snapshot.provenance.chain.links) > 0
    )
    has_explanation = (
        snapshot.explanation is not None
        and len(snapshot.explanation.steps) > 0
    )

    return TrustEvaluation(
        revision_id=revision_id,
        trust=trust,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        has_provenance=has_provenance,
        has_explanation=has_explanation,
    )
