"""Context assembly — builds final prompt from sections with XML escaping."""

from __future__ import annotations

import re

from backend.services.knowledge.context.contracts import (
    Provenance, SOURCES_SYSTEM, SOURCES_MEMORY,
    SECTION_SYSTEM, SECTION_MEMORY, SECTION_KNOWLEDGE, SECTION_QUESTION,
)
from backend.services.knowledge.context.token_counter import count_tokens


# XML closing tags that must be escaped
XML_CLOSE_PATTERN = re.compile(r"<\s*/(system|memory|knowledge|question)\s*>", re.IGNORECASE)
CDATA_CLOSE_PATTERN = re.compile(r"\]\]>")


def escape_xml_content(text: str) -> str:
    """Escape XML closing sequences in injected content.

    Prevents prompt injection via XML tag closing.
    Applied to ALL user-provided content before section assembly.
    """
    text = XML_CLOSE_PATTERN.sub(lambda m: f"\\/{m.group(1)}>", text)
    text = CDATA_CLOSE_PATTERN.sub("]]\\>", text)
    return text


class ContextAssembler:
    """Assemble the final prompt from sections with provenance tracking."""

    def build_prompt(
        self,
        system_prompt: str,
        security_instructions: str,
        memory_text: str,
        knowledge_text: str,
        question: str,
    ) -> tuple[str, dict[str, int], list[Provenance]]:
        """Assemble prompt in FINAL order: System → Security → Memory → Knowledge → Question.

        Returns:
            (prompt, section_tokens, section_provenance)
        """
        provenance: list[Provenance] = []
        section_tokens: dict[str, int] = {}
        parts: list[str] = []

        # 1. System + Security
        sys_escaped = escape_xml_content(system_prompt)
        sec_escaped = escape_xml_content(security_instructions)
        sys_block = f"<system>\n{sys_escaped}\n</system>\n\n<security>\n{sec_escaped}\n</security>"
        parts.append(sys_block)
        tok = count_tokens(sys_block)
        section_tokens[SECTION_SYSTEM] = tok
        provenance.append(Provenance(SOURCES_SYSTEM, "system_config", 1.0, "System prompt + security"))

        # 2. Memory
        mem_escaped = escape_xml_content(memory_text)
        if memory_text.strip():
            mem_block = f"<memory>\n{mem_escaped}\n</memory>"
            parts.append(mem_block)
            tok = count_tokens(mem_block)
            section_tokens[SECTION_MEMORY] = tok
            provenance.append(Provenance(SOURCES_MEMORY, "conversation_history", 1.0, memory_text[:120]))

        # 3. Knowledge
        kn_escaped = escape_xml_content(knowledge_text)
        if knowledge_text.strip():
            kn_block = f"<knowledge>\n{kn_escaped}\n</knowledge>"
            parts.append(kn_block)
            tok = count_tokens(kn_block)
            section_tokens[SECTION_KNOWLEDGE] = tok

        # 4. Question (LAST — recency bias)
        q_escaped = escape_xml_content(question)
        q_block = f"<question>\n{q_escaped}\n</question>"
        parts.append(q_block)
        tok = count_tokens(q_block)
        section_tokens[SECTION_QUESTION] = tok

        prompt = "\n\n".join(parts)
        return prompt, section_tokens, provenance