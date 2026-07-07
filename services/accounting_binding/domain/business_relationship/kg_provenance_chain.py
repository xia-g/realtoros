"""
ProvenanceChain — immutable snapshot of origin chain.

No computation. No tracing. No resolution.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from domain.business_relationship.kg_provenance_link import ProvenanceLink


@dataclass(frozen=True)
class ProvenanceChain:
    """Снимок цепочки происхождения. Immutable."""
    links: tuple[ProvenanceLink, ...] = ()

    @property
    def link_count(self) -> int:
        return len(self.links)