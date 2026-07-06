"""
ChangeExplanation — explainable change in corporate knowledge.

Answers: What changed? Why? Which documents/facts? What confidence?
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChangeExplanation:
    """Explainable description of a knowledge change."""
    summary: str
    evidence: list[str] = field(default_factory=list)
    supporting_documents: list[str] = field(default_factory=list)
    supporting_facts: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "evidence": self.evidence,
            "documents": self.supporting_documents,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class TimelineEntry:
    """One entry in a knowledge timeline."""
    revision_number: int
    change_type: str = ""
    description: str = ""
    timestamp: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "revision": self.revision_number,
            "change": self.change_type,
            "description": self.description,
            "confidence": self.confidence,
        }
