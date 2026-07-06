"""Knowledge source types and trust levels for security layer."""

from __future__ import annotations

from enum import Enum, auto


class KnowledgeSourceType(str, Enum):
    """All supported knowledge source types."""

    DOCUMENT = "document"
    MEMORY = "memory"
    SEARCH_RESULT = "search_result"
    GRAPH_NODE = "graph_node"
    GRAPH_EDGE = "graph_edge"
    REGULATION = "regulation"
    REQUIREMENT_SET = "requirement_set"
    PLAYBOOK = "playbook"
    USER_QUERY = "user_query"


class KnowledgeTrustLevel(str, Enum):
    """Trust classification for knowledge sources.

    TRUSTED: Government regulations, official sources.
    SEMI_TRUSTED: Bank regulations, verified partners.
    UNTRUSTED: User uploads, memory, search results, web content.
    """

    TRUSTED = "trusted"
    SEMI_TRUSTED = "semi_trusted"
    UNTRUSTED = "untrusted"

    @classmethod
    def for_source(cls, source_type: KnowledgeSourceType) -> KnowledgeTrustLevel:
        """Map source type to trust level."""
        mapping = {
            KnowledgeSourceType.REGULATION: cls.TRUSTED,
            KnowledgeSourceType.REQUIREMENT_SET: cls.SEMI_TRUSTED,
            KnowledgeSourceType.PLAYBOOK: cls.SEMI_TRUSTED,
            KnowledgeSourceType.DOCUMENT: cls.UNTRUSTED,
            KnowledgeSourceType.MEMORY: cls.UNTRUSTED,
            KnowledgeSourceType.SEARCH_RESULT: cls.UNTRUSTED,
            KnowledgeSourceType.GRAPH_NODE: cls.UNTRUSTED,
            KnowledgeSourceType.GRAPH_EDGE: cls.UNTRUSTED,
            KnowledgeSourceType.USER_QUERY: cls.UNTRUSTED,
        }
        return mapping.get(source_type, cls.UNTRUSTED)


class SecuritySeverity(str, Enum):
    """Severity levels for security findings."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def score(self) -> int:
        """Numeric score for severity."""
        return {
            SecuritySeverity.LOW: 1,
            SecuritySeverity.MEDIUM: 3,
            SecuritySeverity.HIGH: 6,
            SecuritySeverity.CRITICAL: 10,
        }[self]

    @classmethod
    def from_finding_count(cls, count: int) -> SecuritySeverity:
        """Map finding count to severity."""
        if count >= 6:
            return cls.CRITICAL
        elif count >= 4:
            return cls.HIGH
        elif count >= 2:
            return cls.MEDIUM
        return cls.LOW
