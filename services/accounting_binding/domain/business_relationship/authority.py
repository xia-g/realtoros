"""
Authority Model — how much to trust the source.

Configurable authority levels per document role.
Higher authority = more weight in conflicts and trust.
"""
from __future__ import annotations

from enum import Enum


class AuthorityLevel(str, Enum):
    VERY_LOW = "very_low"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    OFFICIAL = "official"


# Default authority table — configurable, not magic numbers
DEFAULT_AUTHORITY_MAP: dict[str, AuthorityLevel] = {
    # OFFICIAL sources
    "egrn_extract": AuthorityLevel.OFFICIAL,
    "cadastral": AuthorityLevel.OFFICIAL,
    
    # HIGH authority
    "passport": AuthorityLevel.HIGH,
    "sale_contract": AuthorityLevel.HIGH,
    "municipal_contract": AuthorityLevel.HIGH,
    "payment_order": AuthorityLevel.HIGH,
    "bank_statement": AuthorityLevel.HIGH,
    "certificate": AuthorityLevel.HIGH,
    "lease": AuthorityLevel.HIGH,
    "commission": AuthorityLevel.HIGH,
    "agency": AuthorityLevel.HIGH,
    
    # NORMAL authority
    "transfer_act": AuthorityLevel.NORMAL,
    "invoice": AuthorityLevel.NORMAL,
    "receipt": AuthorityLevel.NORMAL,
    "service": AuthorityLevel.NORMAL,
    "amendment": AuthorityLevel.NORMAL,
    "framework": AuthorityLevel.NORMAL,
    "loan": AuthorityLevel.NORMAL,
    "offer": AuthorityLevel.NORMAL,
    
    # LOW authority
    "email": AuthorityLevel.LOW,
    "other_document": AuthorityLevel.LOW,
    
    # VERY_LOW authority
    "free_text": AuthorityLevel.VERY_LOW,
    "unknown": AuthorityLevel.VERY_LOW,
}

# Authority weight in conflict resolution (numeric)
AUTHORITY_WEIGHT: dict[AuthorityLevel, float] = {
    AuthorityLevel.OFFICIAL: 1.0,
    AuthorityLevel.HIGH: 0.75,
    AuthorityLevel.NORMAL: 0.5,
    AuthorityLevel.LOW: 0.25,
    AuthorityLevel.VERY_LOW: 0.1,
}


class AuthorityResolver:
    """Resolve authority level for a document role."""

    def __init__(self, authority_map: dict[str, AuthorityLevel] | None = None):
        self._map = authority_map or dict(DEFAULT_AUTHORITY_MAP)

    def resolve(self, document_role: str) -> AuthorityLevel:
        """Get authority level for a document role."""
        role_lower = document_role.lower() if document_role else "unknown"
        for key, level in self._map.items():
            if key in role_lower or role_lower in key:
                return level
        return AuthorityLevel.VERY_LOW

    def weight(self, document_role: str) -> float:
        """Numeric weight for conflict resolution."""
        level = self.resolve(document_role)
        return AUTHORITY_WEIGHT.get(level, 0.1)

    def compare(self, role_a: str, role_b: str) -> int:
        """Compare two sources. Returns -1, 0, or 1."""
        wa = self.weight(role_a)
        wb = self.weight(role_b)
        if wa < wb: return -1
        if wa > wb: return 1
        return 0
