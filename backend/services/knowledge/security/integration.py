"""Security Integration — ties together detector, sanitizer, audit, and metrics.

Used by Context Builder (P3) and Agent Runtime (P6) to protect all
content before it reaches the AI Provider.

Flow for every content item:
  1. Scan (detect injection patterns, XML attacks)
  2. Sanitize (escape XML, remove control chars)
  3. Audit (log findings, emit events)
  4. Return safe content + scan result
"""

from __future__ import annotations

from backend.config import settings
from backend.core.logging import get_logger
from backend.services.knowledge.security.detector import PromptInjectionDetector
from backend.services.knowledge.security.sanitizer import PromptSanitizer
from backend.services.knowledge.security.contracts import (
    SecurityScanResult, SanitizedContent,
)
from backend.services.knowledge.security.enums import (
    KnowledgeSourceType, SecuritySeverity,
)
from backend.ai.metrics import knowledge_regulation_security_events_total

logger = get_logger("security")


class SecurityService:
    """Unified security service — scan + sanitize + audit for all content types.

    Every piece of content passes through scan() and sanitize() before
    entering Context Builder or AI Provider. No trusted source bypass.
    """

    def __init__(self):
        self.detector = PromptInjectionDetector()
        self.sanitizer = PromptSanitizer()

    def protect(
        self,
        text: str,
        source_type: str = "unknown",
        trust_level: str = "untrusted",
        content_id: str = "",
        version: str | None = None,
    ) -> tuple[SanitizedContent, SecurityScanResult]:
        """Full protection pipeline: scan → sanitize → audit.

        Args:
            text: Content to protect.
            source_type: KnowledgeSourceType value.
            trust_level: KnowledgeTrustLevel value.
            content_id: Content identifier for audit.
            version: Version string (mandatory for REGULATION/REQUIREMENT_SET/PLAYBOOK).

        Returns:
            (sanitized_content, scan_result)
        """
        if not settings.SECURITY_ENABLED:
            return SanitizedContent(content=text), SecurityScanResult()

        # Step 1: Scan for injection
        scan_result = self.detector.scan(
            text=text,
            source_type=source_type,
            trust_level=trust_level,
            content_id=content_id,
        )

        # Step 2: Sanitize (always — even clean content gets escaped)
        sanitized = self.sanitizer.sanitize(text)

        # Step 3: Regulatory-specific audit
        if source_type in (
            KnowledgeSourceType.REGULATION.value,
            KnowledgeSourceType.REQUIREMENT_SET.value,
            KnowledgeSourceType.PLAYBOOK.value,
        ):
            knowledge_regulation_security_events_total.labels(
                event_type="scan",
            ).inc()
            logger.info(
                "knowledge.regulation.detected",
                source_type=source_type,
                trust_level=trust_level,
                version=version or "unknown",
                correlation_id=content_id,
            )

        # Step 4: Emit audit events
        if scan_result.findings:
            patterns_found = [f.pattern_name for f in scan_result.findings]
            logger.info(
                "knowledge.security.scan",
                source_type=source_type,
                trust_level=trust_level,
                finding_count=len(scan_result.findings),
                highest_severity=scan_result.highest_severity.value,
                patterns=patterns_found,
                correlation_id=content_id,
            )

        if sanitized.removed_patterns:
            logger.info(
                "knowledge.security.sanitized",
                source_type=source_type,
                original_length=sanitized.original_length,
                sanitized_length=sanitized.sanitized_length,
                removed_patterns=sanitized.removed_patterns,
                correlation_id=content_id,
            )

        return sanitized, scan_result

    def protect_batch(
        self,
        items: list[dict],
    ) -> tuple[list[dict], list[SecurityScanResult]]:
        """Protect a batch of content items.

        Each item dict must have at least 'content' and 'source_type'.
        Optional: 'trust_level', 'content_id', 'version'.
        """
        safe_items = []
        results = []

        for item in items:
            text = item.get("content", "")
            sanitized, scan_result = self.protect(
                text=text,
                source_type=item.get("source_type", "unknown"),
                trust_level=item.get("trust_level", "untrusted"),
                content_id=item.get("content_id", ""),
                version=item.get("version"),
            )
            item["content"] = sanitized.content
            safe_items.append(item)
            results.append(scan_result)

        return safe_items, results
