"""Content Sanitizer — escapes XML, CDATA, removes control characters, normalizes whitespace.

Preserves all business content. Only removes dangerous fragments.
"""

from __future__ import annotations

import re

from backend.services.knowledge.security.contracts import SanitizedContent
from backend.services.knowledge.security.metrics import knowledge_security_sanitized_total


# XML closing tags to escape — replaces with safe alternatives
XML_CLOSE_PATTERN = re.compile(r"<\s*/\s*(system|security|memory|knowledge|question)\s*>", re.IGNORECASE)
XML_OPEN_PATTERN = re.compile(r"<\s*(system|security|memory|knowledge)(\s[^>]*)?>", re.IGNORECASE)

CDATA_OPEN = re.compile(r"<!\[CDATA\[")
CDATA_CLOSE = re.compile(r"]]>")

NULL_BYTES = re.compile(r"\x00")
INVALID_CONTROLS = re.compile(r"[\x01-\x08\x0b\x0c\x0e-\x1f]")

MULTIPLE_WHITESPACE = re.compile(r"[ \t]{3,}")
MULTIPLE_NEWLINES = re.compile(r"\n{4,}")


class PromptSanitizer:
    """Sanitize content before it enters Context Builder or AI Provider.

    Operations:
    1. XML tag escaping: </system> → &lt;/system&gt;
    2. CDATA escaping: ]]> → ]]&gt;
    3. Null byte removal
    4. Invalid control character removal
    5. Whitespace normalization (preserves structure)
    """

    def sanitize(self, text: str) -> SanitizedContent:
        """Sanitize text content. Never removes business data.

        Returns SanitizedContent with original/sanitized lengths and
        list of removed pattern types.
        """
        if not text:
            return SanitizedContent(content="")

        original = text
        removed: list[str] = []

        # 1. Escape XML closing tags
        new_text, count = XML_CLOSE_PATTERN.subn(
            lambda m: f"&lt;/{m.group(1)}&gt;", text,
        )
        if count > 0:
            removed.append(f"xml_close_tags:{count}")

        # 2. Escape XML opening tags that mimic our structure
        #    (but preserve the content inside)
        new_text, count = XML_OPEN_PATTERN.subn(
            lambda m: f"&lt;{m.group(1)}{m.group(2) or ''}&gt;", new_text,
        )
        if count > 0:
            removed.append(f"xml_open_tags:{count}")

        # 3. Escape CDATA markers
        new_text, count = CDATA_OPEN.subn("&lt;![CDATA[", new_text)
        if count > 0:
            removed.append(f"cdata_open:{count}")
        new_text, count = CDATA_CLOSE.subn("]]&gt;", new_text)
        if count > 0:
            removed.append(f"cdata_close:{count}")

        # 4. Remove null bytes
        new_text, count = NULL_BYTES.subn("", new_text)
        if count > 0:
            removed.append(f"null_bytes:{count}")

        # 5. Remove invalid control characters (keep \n \r \t)
        new_text, count = INVALID_CONTROLS.subn("", new_text)
        if count > 0:
            removed.append(f"invalid_controls:{count}")

        # 6. Normalize Whitespace (preserve structure)
        new_text = MULTIPLE_WHITESPACE.sub("  ", new_text)
        new_text = MULTIPLE_NEWLINES.sub("\n\n\n", new_text)

        result = SanitizedContent(
            original_length=len(original),
            sanitized_length=len(new_text),
            removed_patterns=removed,
            content=new_text,
        )

        if removed:
            knowledge_security_sanitized_total.inc()

        return result
