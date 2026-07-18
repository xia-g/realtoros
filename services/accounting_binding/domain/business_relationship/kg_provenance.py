"""
KnowledgeProvenance — immutable description of knowledge origin.

Pure data. NO build/trace/resolve/find methods.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from domain.business_relationship.kg_provenance_id import ProvenanceId
from domain.business_relationship.kg_provenance_chain import ProvenanceChain
from domain.business_relationship.kg_provenance_metadata import ProvenanceMetadata


@dataclass(frozen=True)
class KnowledgeProvenance:
    """Описание происхождения знания. Immutable. Без логики."""
    provenance_id: ProvenanceId
    chain: ProvenanceChain = field(default_factory=ProvenanceChain)
    metadata: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)