"""
KnowledgeState — immutable snapshot of corporate knowledge at a point in time.

NOT a graph. NOT a document. Description of current knowledge.
Computed from BusinessFacts, Agreements, Relationships, Canonical Entities, KnowledgeGraph.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class TrustSummary:
    """Aggregate trust across all entities."""
    verified_count: int = 0
    high_trust_count: int = 0
    medium_trust_count: int = 0
    low_trust_count: int = 0
    unknown_trust_count: int = 0

    @property
    def average_trust(self) -> float:
        total = (self.verified_count + self.high_trust_count + self.medium_trust_count +
                 self.low_trust_count + self.unknown_trust_count)
        if total == 0:
            return 0.0
        weighted = (self.verified_count * 1.0 + self.high_trust_count * 0.75 +
                    self.medium_trust_count * 0.5 + self.low_trust_count * 0.25)
        return weighted / total


@dataclass(frozen=True)
class KnowledgeState:
    """Current state of corporate knowledge. Immutable."""
    state_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    graph_version: int = 0
    knowledge_version: int = 1

    entity_count: int = 0
    agreement_count: int = 0
    relationship_count: int = 0
    document_count: int = 0
    property_count: int = 0

    trust_summary: TrustSummary = field(default_factory=TrustSummary)
    conflict_count: int = 0

    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "state_id": self.state_id,
            "graph_version": self.graph_version,
            "knowledge_version": self.knowledge_version,
            "entity_count": self.entity_count,
            "agreement_count": self.agreement_count,
            "relationship_count": self.relationship_count,
            "document_count": self.document_count,
            "property_count": self.property_count,
            "trust_avg": self.trust_summary.average_trust,
            "conflict_count": self.conflict_count,
        }
