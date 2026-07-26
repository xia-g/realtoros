"""
Knowledge Governance v1 — models and stateless decision service.

Pure functions over TrustState. No mutation of Knowledge.
No Platform changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from application.capabilities.trust_state import TrustState, TrustEvaluation


# ─── Models ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class GovernanceDecision:
    decision: str              # "APPROVED" | "FLAGGED" | "REJECTED"
    reason: str
    based_on_trust: str        # "VALID" | "WARNING" | "INVALID" | "UNKNOWN"
    structural_errors: int = 0
    structural_warnings: int = 0
    provenance_coverage: float = 0.0


@dataclass(frozen=True)
class GovernanceResult:
    revision_id: str
    decision: GovernanceDecision
    evaluated_at: str


# ─── Rules ────────────────────────────────────────────────────────
# v1: fixed rules. No policy engine.


_RULES: dict[str, tuple[str, str]] = {
    "VALID":   ("APPROVED", "Knowledge is structurally valid. Change is safe."),
    "WARNING": ("FLAGGED",  "Knowledge has non-critical violations. Human review required."),
    "INVALID": ("REJECTED", "Knowledge has critical structural errors. Change blocked."),
    "UNKNOWN": ("FLAGGED",  "Insufficient knowledge data to assess impact. Human review required."),
}


def evaluate_governance(trust: TrustState) -> GovernanceDecision:
    """Evaluate governance decision based on TrustState.

    Deterministic: same trust → same decision.
    No mutation. No storage.
    """
    status = trust.status
    rule = _RULES.get(status, ("FLAGGED", f"Unknown trust status: {status}"))

    return GovernanceDecision(
        decision=rule[0],
        reason=rule[1],
        based_on_trust=status,
        structural_errors=trust.structural_errors,
        structural_warnings=trust.structural_warnings,
        provenance_coverage=trust.provenance_coverage,
    )


def build_governance(
    revision_id: str,
    trust_evaluation: TrustEvaluation,
) -> GovernanceResult:
    """Build complete governance result.

    Args:
        revision_id: The revision being evaluated.
        trust_evaluation: Pre-computed TrustEvaluation.

    Returns:
        GovernanceResult with decision and metadata.
    """
    if trust_evaluation.trust is None:
        return GovernanceResult(
            revision_id=revision_id,
            decision=GovernanceDecision(
                decision="FLAGGED",
                reason="Cannot evaluate governance: no trust data available",
                based_on_trust="UNKNOWN",
            ),
            evaluated_at=datetime.now(timezone.utc).isoformat(),
        )

    decision = evaluate_governance(trust_evaluation.trust)

    return GovernanceResult(
        revision_id=revision_id,
        decision=decision,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
    )
