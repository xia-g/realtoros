"""Security contracts — dataclasses for findings, results, sanitized content."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from backend.services.knowledge.security.enums import (
    KnowledgeSourceType, KnowledgeTrustLevel, SecuritySeverity,
)


@dataclass
class SecurityFinding:
    """A single security finding from scanning content."""

    pattern_name: str
    category: str
    severity: SecuritySeverity
    matched_text: str
    start_offset: int = 0
    end_offset: int = 0

    @property
    def snippet(self) -> str:
        """Return a shortened snippet of matched text."""
        if len(self.matched_text) <= 100:
            return self.matched_text
        return self.matched_text[:47] + "..." + self.matched_text[-47:]


@dataclass
class SecurityScanResult:
    """Result of scanning a piece of content for security threats."""

    content_id: str = ""
    source_type: str = ""
    trust_level: str = ""
    findings: list[SecurityFinding] = field(default_factory=list)
    highest_severity: SecuritySeverity = SecuritySeverity.LOW
    score: int = 0
    is_suspicious: bool = False

    def __post_init__(self):
        if self.findings:
            self.highest_severity = max(
                (f.severity for f in self.findings),
                key=lambda s: s.score(),
            )
            self.score = sum(f.severity.score() for f in self.findings)
            self.is_suspicious = self.highest_severity in (
                SecuritySeverity.HIGH, SecuritySeverity.CRITICAL,
            )


@dataclass
class SanitizedContent:
    """Sanitized content with metadata about what was removed."""

    original_length: int = 0
    sanitized_length: int = 0
    removed_patterns: list[str] = field(default_factory=list)
    content: str = ""
