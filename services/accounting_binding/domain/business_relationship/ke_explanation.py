"""
GraphExplanation — immutable description of knowledge provenance.

Pure data. NO analysis. NO search. NO reasoning.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from domain.business_relationship.ke_explanation_id import ExplanationId
from domain.business_relationship.ke_explanation_step import ExplanationStep
from domain.business_relationship.ke_explanation_metadata import ExplanationMetadata
from domain.business_relationship.kg_identifiers import GraphNodeId


@dataclass(frozen=True)
class GraphExplanation:
    """Объяснение знания. Immutable. Без логики."""
    explanation_id: ExplanationId
    graph_node_id: GraphNodeId
    steps: tuple[ExplanationStep, ...] = ()
    overall_confidence: float = 1.0
    metadata: ExplanationMetadata = field(default_factory=ExplanationMetadata)

    @property
    def step_count(self) -> int:
        return len(self.steps)
