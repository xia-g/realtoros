"""
ConflictDetector — detects knowledge conflicts from deltas.

Deterministic. No resolution. No mutation.
Only classifies conflicts from change data.
"""
from __future__ import annotations

from datetime import datetime

from domain.business_relationship.ke_enums import ConflictType
from domain.business_relationship.ke_delta import KnowledgeDelta
from domain.business_relationship.ke_conflict import KnowledgeConflict


class ConflictDetector:
    """Определяет наличие конфликтов в изменениях знаний.

    Stateless. Deterministic. NO resolution.
    """

    @staticmethod
    def detect(delta: KnowledgeDelta) -> list[KnowledgeConflict]:
        """Detect conflicts from a single delta.

        Rules (deterministic, no heuristics):
          - Same entity, same field with different values → CONFLICT (VALUE)
          - Ownership field changing → CONFLICT (OWNERSHIP)
          - Participant field changing → CONFLICT (PARTICIPANT)
          - Period field changing → CONFLICT (PERIOD)
        """
        conflicts: list[KnowledgeConflict] = []
        now = datetime.utcnow()

        for change in delta.changes:
            # Ownership conflicts
            if "owner" in change.field.lower() or "ownership" in change.field.lower():
                conflicts.append(KnowledgeConflict(
                    conflict_type=ConflictType.OWNERSHIP,
                    entity_id=delta.entity_id,
                    conflicting_sources=(str(change.old_value), str(change.new_value)),
                    detected_at=now,
                    description=f"Ownership change: {change.old_value} -> {change.new_value}",
                ))

            # Participant conflicts
            elif "participant" in change.field.lower() or "party" in change.field.lower():
                conflicts.append(KnowledgeConflict(
                    conflict_type=ConflictType.PARTICIPANT,
                    entity_id=delta.entity_id,
                    conflicting_sources=(str(change.old_value), str(change.new_value)),
                    detected_at=now,
                    description=f"Participant change: {change.old_value} -> {change.new_value}",
                ))

            # Period conflicts
            elif "period" in change.field.lower() or "date" in change.field.lower():
                conflicts.append(KnowledgeConflict(
                    conflict_type=ConflictType.PERIOD,
                    entity_id=delta.entity_id,
                    conflicting_sources=(str(change.old_value), str(change.new_value)),
                    detected_at=now,
                    description=f"Period change: {change.old_value} -> {change.new_value}",
                ))

            # Generic value conflicts
            elif change.old_value is not None and change.new_value is not None and change.old_value != change.new_value:
                conflicts.append(KnowledgeConflict(
                    conflict_type=ConflictType.VALUE,
                    entity_id=delta.entity_id,
                    conflicting_sources=(str(change.old_value), str(change.new_value)),
                    detected_at=now,
                    description=f"Value conflict in '{change.field}': {change.old_value} vs {change.new_value}",
                ))

        return conflicts
