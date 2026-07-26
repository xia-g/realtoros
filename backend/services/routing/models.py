"""Stream 3 — Routing domain models and engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ─── Models ──────────────────────────────────────────────────────


@dataclass
class RoutingRule:
    rule_id: str
    name: str
    document_type: str
    condition: str
    destination: str
    priority: int
    min_confidence: float
    needs_approval: bool
    active: bool = True


@dataclass
class RoutingDecision:
    decision_id: str
    document_id: str
    rule_id: str = ""
    destination: str = ""
    status: str = "PENDING"
    confidence: float = 0.0
    matched_entities: dict = field(default_factory=dict)
    needs_approval: bool = False
    created_at: datetime | None = None
    routed_at: datetime | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def is_final(self) -> bool:
        return self.status in ("ROUTED", "FAILED", "OVERRIDDEN")


@dataclass
class RoutingResult:
    matched: bool
    destination: str
    rule: str = ""
    rule_id: str = ""
    confidence: float = 0.0
    needs_approval: bool = False


# ─── Rules ────────────────────────────────────────────────────────


DEFAULT_ROUTING_RULES: list[RoutingRule] = [
    RoutingRule(
        rule_id="inv-acc",
        name="Invoice to Accounting",
        document_type="invoice",
        condition="confidence >= 0.7",
        destination="accounting",
        priority=10,
        min_confidence=0.7,
        needs_approval=False,
    ),
    RoutingRule(
        rule_id="act-acc",
        name="Act to Accounting",
        document_type="act",
        condition="confidence >= 0.7",
        destination="accounting",
        priority=10,
        min_confidence=0.7,
        needs_approval=False,
    ),
    RoutingRule(
        rule_id="stm-acc",
        name="Bank Statement to Accounting",
        document_type="bank_statement",
        condition="confidence >= 0.6",
        destination="accounting",
        priority=10,
        min_confidence=0.6,
        needs_approval=False,
    ),
    RoutingRule(
        rule_id="cnt-deal",
        name="Contract to Deal Workflow",
        document_type="contract",
        condition="confidence >= 0.6",
        destination="deal",
        priority=10,
        min_confidence=0.6,
        needs_approval=True,
    ),
    RoutingRule(
        rule_id="pas-crm",
        name="Passport to CRM",
        document_type="passport",
        condition="True",
        destination="crm",
        priority=10,
        min_confidence=0.0,
        needs_approval=True,
    ),
    RoutingRule(
        rule_id="def-review",
        name="Default — Manual Review",
        document_type="unknown",
        condition="True",
        destination="needs_review",
        priority=0,
        min_confidence=0.0,
        needs_approval=True,
    ),
    RoutingRule(
        rule_id="receipt-acc",
        name="Receipt to Accounting",
        document_type="receipt",
        condition="confidence >= 0.6",
        destination="accounting",
        priority=10,
        min_confidence=0.6,
        needs_approval=False,
    ),
    RoutingRule(
        rule_id="poa-crm",
        name="Power of Attorney to CRM",
        document_type="power_of_attorney",
        condition="confidence >= 0.5",
        destination="crm",
        priority=10,
        min_confidence=0.5,
        needs_approval=True,
    ),
]


# ─── Routing Engine ──────────────────────────────────────────────


class RoutingEngine:
    """Evaluate routing rules against document profile."""

    def __init__(self, rules: list[RoutingRule] | None = None):
        self._rules = rules or DEFAULT_ROUTING_RULES

    def evaluate(self, profile: dict) -> RoutingResult:
        """Evaluate routing rules against document profile.

        Args:
            profile: Document.profile dict with document_type, confidence, etc.

        Returns:
            RoutingResult with destination and decision metadata.
        """
        doc_type = profile.get("document_type", "unknown")
        confidence = float(profile.get("confidence", 0.0))
        extraction_confidence = float(profile.get("extraction_confidence", 0.0))
        classification_confidence = float(profile.get("classification_confidence", 0.0))

        # Use best available confidence
        best_confidence = max(confidence, extraction_confidence, classification_confidence)

        # Find matching rules
        candidates = [
            r for r in self._rules
            if r.active and (
                r.document_type == doc_type or
                (doc_type == "unknown" and r.document_type == "unknown")
            )
            and best_confidence >= r.min_confidence
        ]

        if not candidates:
            # Fallback to default
            default = next((r for r in self._rules if r.document_type == "unknown"), None)
            if default:
                return RoutingResult(
                    matched=False,
                    destination=default.destination,
                    rule=default.name,
                    rule_id=default.rule_id,
                    confidence=best_confidence,
                    needs_approval=default.needs_approval,
                )
            return RoutingResult(
                matched=False,
                destination="needs_review",
                confidence=best_confidence,
            )

        # Pick highest priority, then highest confidence threshold
        best = max(candidates, key=lambda r: (r.priority, r.min_confidence))
        return RoutingResult(
            matched=True,
            destination=best.destination,
            rule=best.name,
            rule_id=best.rule_id,
            confidence=best_confidence,
            needs_approval=best.needs_approval,
        )
