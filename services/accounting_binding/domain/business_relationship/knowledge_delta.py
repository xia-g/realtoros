"""
KnowledgeChange + KnowledgeDelta — tracked changes between revisions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from domain.business_relationship.knowledge_revision import KnowledgeRevision


class KnowledgeChangeType(str, Enum):
    ENTITY_CREATED = "entity_created"
    ENTITY_UPDATED = "entity_updated"
    AGREEMENT_CREATED = "agreement_created"
    AGREEMENT_UPDATED = "agreement_updated"
    RELATIONSHIP_CREATED = "relationship_created"
    PROPERTY_LINKED = "property_linked"
    DOCUMENT_ATTACHED = "document_attached"
    FACT_CONFIRMED = "fact_confirmed"
    TRUST_INCREASED = "trust_increased"
    OWNERSHIP_CONFIRMED = "ownership_confirmed"
    PAYMENT_CONFIRMED = "payment_confirmed"
    REGISTRATION_CONFIRMED = "registration_confirmed"


@dataclass(frozen=True)
class KnowledgeChange:
    """Atomic change in knowledge. Immutable."""
    change_type: KnowledgeChangeType
    object_id: str
    description: str
    confidence: float = 1.0
    source_document_ids: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "type": self.change_type.value,
            "object": self.object_id,
            "description": self.description,
            "confidence": self.confidence,
            "documents": self.source_document_ids,
        }


class ChangeCategory(str, Enum):
    ENTITIES = "entities"
    AGREEMENTS = "agreements"
    PROPERTIES = "properties"
    RELATIONSHIPS = "relationships"
    DOCUMENTS = "documents"
    TRUST = "trust"
    OWNERSHIP = "ownership"
    PAYMENTS = "payments"
    REGISTRATION = "registration"

    @classmethod
    def from_change_type(cls, ct: KnowledgeChangeType) -> ChangeCategory:
        mapping = {
            KnowledgeChangeType.ENTITY_CREATED: cls.ENTITIES,
            KnowledgeChangeType.ENTITY_UPDATED: cls.ENTITIES,
            KnowledgeChangeType.AGREEMENT_CREATED: cls.AGREEMENTS,
            KnowledgeChangeType.AGREEMENT_UPDATED: cls.AGREEMENTS,
            KnowledgeChangeType.RELATIONSHIP_CREATED: cls.RELATIONSHIPS,
            KnowledgeChangeType.PROPERTY_LINKED: cls.PROPERTIES,
            KnowledgeChangeType.DOCUMENT_ATTACHED: cls.DOCUMENTS,
            KnowledgeChangeType.FACT_CONFIRMED: cls.TRUST,
            KnowledgeChangeType.TRUST_INCREASED: cls.TRUST,
            KnowledgeChangeType.OWNERSHIP_CONFIRMED: cls.OWNERSHIP,
            KnowledgeChangeType.PAYMENT_CONFIRMED: cls.PAYMENTS,
            KnowledgeChangeType.REGISTRATION_CONFIRMED: cls.REGISTRATION,
        }
        return mapping.get(ct, cls.DOCUMENTS)


@dataclass(frozen=True)
class KnowledgeDelta:
    """Difference between two revisions. Immutable and non-destructive."""
    from_revision: int
    to_revision: int
    changes: list[KnowledgeChange] = field(default_factory=list)
    summary: str = ""
    confidence: float = 1.0
    created_at: datetime = field(default_factory=datetime.utcnow)

    def by_category(self) -> dict[ChangeCategory, list[KnowledgeChange]]:
        result: dict[ChangeCategory, list[KnowledgeChange]] = {}
        for c in self.changes:
            cat = ChangeCategory.from_change_type(c.change_type)
            result.setdefault(cat, []).append(c)
        return result

    @property
    def has_changes(self) -> bool:
        return len(self.changes) > 0

    def to_dict(self) -> dict:
        return {
            "from_revision": self.from_revision,
            "to_revision": self.to_revision,
            "changes": [c.to_dict() for c in self.changes],
            "summary": self.summary,
            "confidence": self.confidence,
            "categories": {k.value: len(v) for k, v in self.by_category().items()},
        }

    @classmethod
    def compute(
        cls,
        old_revision: KnowledgeRevision,
        new_revision: KnowledgeRevision,
        changes: list[KnowledgeChange],
    ) -> KnowledgeDelta:
        s = f"v{old_revision.revision_number} → v{new_revision.revision_number}: {len(changes)} changes"
        return cls(
            from_revision=old_revision.revision_number,
            to_revision=new_revision.revision_number,
            changes=changes,
            summary=s,
        )
