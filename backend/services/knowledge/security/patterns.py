"""Centralized injection pattern catalog — 32 patterns across 7 categories.

Patterns are compiled once at module load time.
Each pattern is a (name, category, regex, severity) tuple.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from backend.services.knowledge.security.enums import SecuritySeverity


class PatternDef(NamedTuple):
    """A single injection pattern definition."""
    name: str
    category: str
    pattern: re.Pattern
    severity: SecuritySeverity


def _c(name: str, cat: str, raw: str, sev: SecuritySeverity) -> PatternDef:
    """Helper to create a case-insensitive compiled PatternDef."""
    return PatternDef(
        name=name,
        category=cat,
        pattern=re.compile(raw, re.IGNORECASE | re.DOTALL),
        severity=sev,
    )


# ── 32 patterns across 7 categories ──

PATTERN_CATALOG: list[PatternDef] = [

    # ── Instruction Override (7) ──
    _c("ignore_previous_instructions", "instruction_override",
       r"ignore\s+(all\s+)?previous\s+(instructions|prompts?|commands?)", SecuritySeverity.CRITICAL),
    _c("ignore_all_instructions", "instruction_override",
       r"ignore\s+all\s+(instructions|prompts?|commands?)", SecuritySeverity.CRITICAL),
    _c("forget_previous_instructions", "instruction_override",
       r"forget\s+(all\s+)?(previous\s+)?(instructions|prompts?|context)", SecuritySeverity.HIGH),
    _c("new_instructions", "instruction_override",
       r"^(here\s+are\s+)?new\s+instructions\s*:", SecuritySeverity.HIGH),
    _c("override_instructions", "instruction_override",
       r"override\s+(instructions|prompts?|commands?|system)", SecuritySeverity.CRITICAL),
    _c("system_instructions", "instruction_override",
       r"(system|developer)\s+instructions?\s*:", SecuritySeverity.HIGH),
    _c("custom_instructions", "instruction_override",
       r"(my|your|new)\s+(custom\s+)?instructions?\s+(are|follow|override)", SecuritySeverity.HIGH),

    # ── Prompt Disclosure (5) ──
    _c("show_hidden_prompt", "prompt_disclosure",
       r"(show|display|reveal|print|output)\s+(hidden\s+)?(prompt|instructions?)",
       SecuritySeverity.CRITICAL),
    _c("show_system_prompt", "prompt_disclosure",
       r"(show|display|reveal|print|output)\s+(system|initial|original)\s+(prompt|instructions?)",
       SecuritySeverity.CRITICAL),
    _c("print_prompt", "prompt_disclosure",
       r"print\s+(the\s+)?(full\s+)?prompt", SecuritySeverity.HIGH),
    _c("reveal_prompt", "prompt_disclosure",
       r"reveal\s+(the\s+)?(prompt|instructions?)", SecuritySeverity.CRITICAL),
    _c("reveal_instructions", "prompt_disclosure",
       r"what\s+(are|were)\s+(your|the)\s+instructions", SecuritySeverity.HIGH),

    # ── Role Manipulation (6) ──
    _c("act_as", "role_manipulation",
       r"act\s+as\s+(if\s+you\s+are\s+)?(a\s+|an\s+)?(admin|root|master|system|developer)",
       SecuritySeverity.HIGH),
    _c("pretend_to_be", "role_manipulation",
       r"pretend\s+(to\s+be|that\s+you\s+are)\s+(a\s+|an\s+)?(admin|root|master|developer)",
       SecuritySeverity.MEDIUM),
    _c("you_are_now", "role_manipulation",
       r"you\s+are\s+now\s+(a\s+|an\s+)?(admin|root|master|developer|system)",
       SecuritySeverity.HIGH),
    _c("become_admin", "role_manipulation",
       r"become\s+(a\s+|an\s+)?(admin|root|superuser)", SecuritySeverity.HIGH),
    _c("become_root", "role_manipulation",
       r"become\s+root", SecuritySeverity.HIGH),
    _c("administrator_mode", "role_manipulation",
       r"(admin|administrator|sudo|superuser)\s+mode", SecuritySeverity.MEDIUM),

    # ── Tool Abuse (5) ──
    _c("call_tool", "tool_abuse",
       r"call\s+(the\s+)?tool\s+", SecuritySeverity.MEDIUM),
    _c("invoke_tool", "tool_abuse",
       r"invoke\s+(the\s+)?(tool|function)\s+", SecuritySeverity.MEDIUM),
    _c("execute_tool", "tool_abuse",
       r"execute\s+(the\s+)?(tool|function|command)\s+", SecuritySeverity.HIGH),
    _c("run_command", "tool_abuse",
       r"run\s+(the\s+)?(command|script|shell)\s+", SecuritySeverity.HIGH),
    _c("invoke_function", "tool_abuse",
       r"invoke\s+(the\s+)?function\s+", SecuritySeverity.MEDIUM),

    # ── Jailbreak (5) ──
    _c("dan_mode", "jailbreak",
       r"\bDAN\b", SecuritySeverity.HIGH),
    _c("developer_mode", "jailbreak",
       r"developer\s+mode", SecuritySeverity.HIGH),
    _c("god_mode", "jailbreak",
       r"(god|omniscient|unrestricted)\s+mode", SecuritySeverity.CRITICAL),
    _c("do_anything_now", "jailbreak",
       r"do\s+anything\s+now", SecuritySeverity.HIGH),
    _c("unrestricted_mode", "jailbreak",
       r"(unrestricted|no\s+(limits|restrictions|boundaries|rules))",
       SecuritySeverity.HIGH),

    # ── Hidden Prompts (4) ──
    _c("begin_prompt", "hidden_prompt",
       r"\bBEGIN\s+PROMPT\b", SecuritySeverity.MEDIUM),
    _c("end_prompt", "hidden_prompt",
       r"\bEND\s+PROMPT\b", SecuritySeverity.MEDIUM),
    _c("confidential_prompt", "hidden_prompt",
       r"\bCONFIDENTIAL\s+(PROMPT|INSTRUCTIONS)\b", SecuritySeverity.HIGH),
    _c("internal_instructions", "hidden_prompt",
       r"\bINTERNAL\s+(INSTRUCTIONS|PROMPT|GUIDELINES)\b", SecuritySeverity.HIGH),
]

# Immediate CRITICAL patterns (fast-path for the most dangerous ones)
IMMEDIATE_CRITICAL = {
    p.name for p in PATTERN_CATALOG
    if p.severity == SecuritySeverity.CRITICAL
}
