"""
Knowledge Governance — stateless unit tests.

Tests evaluate_governance() directly. No database needed.
"""
from __future__ import annotations

import sys
sys.path.insert(0, "/home/xiag/real-estate-os/services/accounting_binding")

from application.capabilities.trust_state import TrustState
from application.capabilities.governance import evaluate_governance


def _trust(status: str, errors: int = 0, warnings: int = 0, coverage: float = 1.0) -> TrustState:
    return TrustState(
        status=status,
        reasons=(),
        structural_errors=errors,
        structural_warnings=warnings,
        node_count=5,
        edge_count=3,
        provenance_coverage=coverage,
    )


class TestGovernance:

    def test_valid_approved(self):
        t = _trust("VALID")
        d = evaluate_governance(t)
        assert d.decision == "APPROVED"

    def test_warning_flagged(self):
        t = _trust("WARNING", warnings=2)
        d = evaluate_governance(t)
        assert d.decision == "FLAGGED"

    def test_invalid_rejected(self):
        t = _trust("INVALID", errors=2)
        d = evaluate_governance(t)
        assert d.decision == "REJECTED"

    def test_unknown_flagged(self):
        t = _trust("UNKNOWN")
        d = evaluate_governance(t)
        assert d.decision == "FLAGGED"

    def test_reason_returned(self):
        t = _trust("INVALID", errors=1)
        d = evaluate_governance(t)
        assert len(d.reason) > 0
        assert "INVALID" in d.reason or "error" in d.reason.lower()

    def test_deterministic(self):
        t = _trust("VALID")
        d1 = evaluate_governance(t)
        d2 = evaluate_governance(t)
        assert d1.decision == d2.decision
        assert d1.reason == d2.reason

    def test_structural_counts_passed(self):
        t = _trust("INVALID", errors=3, warnings=1, coverage=0.5)
        d = evaluate_governance(t)
        assert d.structural_errors == 3
        assert d.structural_warnings == 1
        assert d.provenance_coverage == 0.5

    def test_based_on_trust(self):
        t = _trust("WARNING")
        d = evaluate_governance(t)
        assert d.based_on_trust == "WARNING"
