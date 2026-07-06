""""Knowledge Agent Security Layer.

Protects prompts, memory, search results, OCR output, graph content,
CRM entities, regulations, requirement sets and playbooks from:
- Prompt injection
- Context poisoning
- XML injection
- Instruction override attacks
- Hidden prompts
- Tool abuse attempts
- Jailbreak attempts
- Regulatory knowledge poisoning

All content is scanned BEFORE entering Context Builder or AI Provider.
"""

from backend.services.knowledge.security.enums import (
    KnowledgeSourceType, KnowledgeTrustLevel, SecuritySeverity,
)
from backend.services.knowledge.security.contracts import (
    SecurityFinding, SecurityScanResult, SanitizedContent,
)
from backend.services.knowledge.security.detector import PromptInjectionDetector
from backend.services.knowledge.security.sanitizer import PromptSanitizer
from backend.services.knowledge.security.patterns import PATTERN_CATALOG

from backend.services.knowledge.security.integration import SecurityService

__all__ = [
    "KnowledgeSourceType",
    "KnowledgeTrustLevel",
    "SecuritySeverity",
    "SecurityFinding",
    "SecurityScanResult",
    "SanitizedContent",
    "PromptInjectionDetector",
    "PromptSanitizer",
    "SecurityService",
    "PATTERN_CATALOG",
]
