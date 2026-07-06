"""Prompt Injection Detector — scans content for injection patterns.

Scan pipeline:
1. Text patterns (32 patterns, 7 categories from PATTERN_CATALOG)
2. XML injection detection
3. Severity aggregation
"""

from __future__ import annotations

import time

from backend.core.logging import get_logger
from backend.services.knowledge.security.enums import (
    KnowledgeSourceType, KnowledgeTrustLevel, SecuritySeverity,
)
from backend.services.knowledge.security.contracts import (
    SecurityFinding, SecurityScanResult,
)
from backend.services.knowledge.security.patterns import (
    PATTERN_CATALOG, IMMEDIATE_CRITICAL,
)
from backend.services.knowledge.security.xml_detector import XMLInjectionDetector
from backend.services.knowledge.security.metrics import (
    knowledge_security_scans_total,
    knowledge_security_findings_total,
    knowledge_security_critical_total,
    knowledge_security_scan_duration_seconds,
    knowledge_injection_attempts_total,
)
from backend.ai.metrics import ai_prompt_injection_detected_total

logger = get_logger("security")


class PromptInjectionDetector:
    """Scan content for prompt injection, jailbreaks, and XML attacks.

    All content types (documents, memory, search results, graph, regulations)
    go through this detector. No trusted-source bypass.
    """

    def __init__(self):
        self.xml_detector = XMLInjectionDetector()

    def scan(
        self,
        text: str,
        source_type: str = "unknown",
        trust_level: str = "untrusted",
        content_id: str = "",
    ) -> SecurityScanResult:
        """Scan a piece of text for security threats.

        Args:
            text: Content to scan.
            source_type: KnowledgeSourceType value.
            trust_level: KnowledgeTrustLevel value.
            content_id: Optional identifier for the content.

        Returns:
            SecurityScanResult with findings and severity.
        """
        start = time.monotonic()
        findings: list[SecurityFinding] = []

        if not text:
            elapsed = time.monotonic() - start
            knowledge_security_scan_duration_seconds.observe(elapsed)
            return SecurityScanResult(
                content_id=content_id,
                source_type=source_type,
                trust_level=trust_level,
            )

        # ── Step 1: Pattern matching (32 patterns) ──
        for pdef in PATTERN_CATALOG:
            for match in pdef.pattern.finditer(text):
                findings.append(SecurityFinding(
                    pattern_name=pdef.name,
                    category=pdef.category,
                    severity=pdef.severity,
                    matched_text=match.group(),
                    start_offset=match.start(),
                    end_offset=match.end(),
                ))

        # ── Step 2: XML injection detection ──
        xml_findings = self.xml_detector.scan(text)
        findings.extend(xml_findings)

        # ── Step 3: Build result ──
        result = SecurityScanResult(
            content_id=content_id,
            source_type=source_type,
            trust_level=trust_level,
            findings=findings,
        )

        # ── Update metrics ──
        elapsed = time.monotonic() - start
        knowledge_security_scans_total.inc()
        knowledge_security_scan_duration_seconds.observe(elapsed)
        knowledge_security_findings_total.inc(len(findings))
        ai_prompt_injection_detected_total.labels(
            severity=result.highest_severity.value,
        ).inc()

        if result.highest_severity == SecuritySeverity.CRITICAL:
            knowledge_security_critical_total.inc()
            knowledge_injection_attempts_total.inc()

        # ── Log findings ──
        if findings:
            logger.info(
                "knowledge.security.detected",
                source_type=source_type,
                trust_level=trust_level,
                finding_count=len(findings),
                highest_severity=result.highest_severity.value,
                is_suspicious=result.is_suspicious,
                correlation_id=content_id,
            )

        return result
