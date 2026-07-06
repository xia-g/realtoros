"""XML Injection Detector — detects closing tag injection, CDATA, malformed XML."""

from __future__ import annotations

import re

from backend.services.knowledge.security.enums import SecuritySeverity
from backend.services.knowledge.security.contracts import SecurityFinding


# XML closing tags that must never appear in user/memory content
XML_CLOSE_TAGS = re.compile(
    r"<\s*/\s*(system|security|memory|knowledge|question)\s*>",
    re.IGNORECASE,
)
CDATA_CLOSE = re.compile(r"]]\s*>")
NESTED_BLOCK = re.compile(
    r"<\s*(system|security|memory|knowledge)\s*>",
    re.IGNORECASE,
)


class XMLInjectionDetector:
    """Detect XML injection attempts in knowledge content."""

    def scan(self, text: str) -> list[SecurityFinding]:
        """Scan text for XML injection patterns.

        Returns a list of SecurityFinding (empty list = clean).
        """
        findings: list[SecurityFinding] = []

        # 1. Detect closing tag injection
        for match in XML_CLOSE_TAGS.finditer(text):
            tag = match.group(1)
            findings.append(SecurityFinding(
                pattern_name=f"xml_close_tag_{tag}",
                category="xml_injection",
                severity=SecuritySeverity.CRITICAL,
                matched_text=match.group(),
                start_offset=match.start(),
                end_offset=match.end(),
            ))

        # 2. Detect CDATA injection
        for match in CDATA_CLOSE.finditer(text):
            findings.append(SecurityFinding(
                pattern_name="xml_cdata_close",
                category="xml_injection",
                severity=SecuritySeverity.HIGH,
                matched_text=match.group(),
                start_offset=match.start(),
                end_offset=match.end(),
            ))

        # 3. Detect nested prompt blocks (content trying to open new XML blocks)
        for match in NESTED_BLOCK.finditer(text):
            tag = match.group(1)
            findings.append(SecurityFinding(
                pattern_name=f"xml_nested_block_{tag}",
                category="xml_injection",
                severity=SecuritySeverity.HIGH,
                matched_text=match.group(),
                start_offset=match.start(),
                end_offset=match.end(),
            ))

        return findings
