"""
ChangeTracker — service for tracking knowledge evolution.

Creates revisions, computes deltas, builds timelines, explains changes.
All in-memory. NO DB writes. Append-only revisions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from domain.business_relationship.knowledge_state import KnowledgeState, TrustSummary
from domain.business_relationship.knowledge_revision import KnowledgeRevision
from domain.business_relationship.knowledge_delta import (
    KnowledgeChange, KnowledgeChangeType, KnowledgeDelta, ChangeCategory,
)
from domain.business_relationship.state_explanation import ChangeExplanation, TimelineEntry


@dataclass
class ChangeTracker:
    """Tracks knowledge evolution through immutable revisions.

    create_revision(state, documents) → append-only revision
    calculate_delta(old, new) → non-destructive diff
    summarize_changes(delta) → human-readable summary
    get_timeline(entity_id) → chronological history
    explain_change(revision, change) → why this happened
    """

    _revisions: list[KnowledgeRevision] = field(default_factory=list)
    _revision_counter: int = 0
    _timeline: dict[str, list[TimelineEntry]] = field(default_factory=dict)  # entity → timeline

    def create_revision(
        self,
        state: KnowledgeState,
        document_ids: list[str] | None = None,
        changes: list[KnowledgeChange] | None = None,
    ) -> KnowledgeRevision:
        """Create a new immutable revision. Monotonic."""
        self._revision_counter += 1
        prev = self._revisions[-1].revision_number if self._revisions else None

        # Build summary from changes
        changes = changes or []
        if changes:
            cats = self._categorize(changes)
            parts = [f"+{v} {k.value}" for k, v in cats.items()]
            summary = " ".join(parts) if parts else "no changes"
        else:
            summary = ""

        revision = KnowledgeRevision(
            revision_number=self._revision_counter,
            previous_revision=prev,
            state=state,
            created_from_documents=document_ids or [],
            summary=summary,
        )

        self._revisions.append(revision)

        # Record timeline entries
        for change in changes:
            if change.object_id:
                self._timeline.setdefault(change.object_id, []).append(TimelineEntry(
                    revision_number=revision.revision_number,
                    change_type=change.change_type.value,
                    description=change.description,
                    timestamp=datetime.utcnow().isoformat(),
                    confidence=change.confidence,
                ))

        return revision

    def calculate_delta(self, old_revision: KnowledgeRevision,
                        new_revision: KnowledgeRevision,
                        changes: list[KnowledgeChange]) -> KnowledgeDelta:
        """Non-destructive diff between two revisions."""
        return KnowledgeDelta.compute(old_revision, new_revision, changes)

    def get_timeline(self, entity_id: str) -> list[TimelineEntry]:
        """Chronological history for a specific entity."""
        return list(self._timeline.get(entity_id, []))

    def all_timelines(self) -> dict[str, list[TimelineEntry]]:
        return dict(self._timeline)

    def explain_change(self, change: KnowledgeChange) -> ChangeExplanation:
        """Explain why a change happened."""
        evidence = [f"{change.change_type.value}: {change.description}"]
        return ChangeExplanation(
            summary=change.description,
            evidence=evidence,
            supporting_documents=change.source_document_ids,
            confidence=change.confidence,
        )

    @property
    def latest_revision(self) -> KnowledgeRevision | None:
        return self._revisions[-1] if self._revisions else None

    @property
    def revision_count(self) -> int:
        return len(self._revisions)

    def _categorize(self, changes: list[KnowledgeChange]) -> dict[ChangeCategory, int]:
        result: dict[ChangeCategory, int] = {}
        for c in changes:
            cat = ChangeCategory.from_change_type(c.change_type)
            result[cat] = result.get(cat, 0) + 1
        return result
