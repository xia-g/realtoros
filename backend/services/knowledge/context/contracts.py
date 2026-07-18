"""Context Builder — core contracts.

All data classes used by ContextBuilderService.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(slots=True)
class Provenance:
    """Structured provenance for every context item.

    Enables debugging, source citations, explainability.
    """
    source_type: str       # "document", "chunk", "graph", "memory", "system"
    source_id: UUID | str  # UUID of entity/chunk
    score: float           # relevance score (0.0-1.0)
    snippet: str = ""      # first 120 chars for debugging (not sent to LLM)


SOURCES_DOCUMENT = "document"
SOURCES_CHUNK = "chunk"
SOURCES_GRAPH = "graph"
SOURCES_MEMORY = "memory"
SOURCES_SYSTEM = "system"

# ── Entity type constants ──
ENTITY_CLIENT = "client"
ENTITY_PROPERTY = "property"
ENTITY_DEAL = "deal"
ENTITY_LEAD = "lead"
ENTITY_DOCUMENT = "document"
ENTITY_DOCUMENT_CHUNK = "document_chunk"

# Items from search results need an explicit entity_id for R6 cross-check
ENTITY_ID_FIELD = "entity_id"

# Section identifiers for token counting
SECTION_SYSTEM = "system"
SECTION_MEMORY = "memory"
SECTION_KNOWLEDGE = "knowledge"
SECTION_QUESTION = "question"


@dataclass
class ContextBuilderInput:
    query: str
    user_id: UUID
    session_id: UUID | None = None
    correlation_id: str = ""


@dataclass
class ContextBuilderOutput:
    prompt: str
    token_count: int
    entities: list[str]        # list of entity IDs referenced
    provenance: list[Provenance]
    dedup_ratio: float         # removed / total items before dedup
    truncated: bool            # True if truncation occurred
    section_tokens: dict = field(default_factory=dict)  # tokens per section


# ── Hard limits (from ADR-0015 D2) ──
HARD_CAP_TOKENS = 6800
RESERVE_TOKENS = 1200         # reserved for model response (15% of 8K window)

BUDGET_SYSTEM = 1000
BUDGET_MEMORY = 1000
BUDGET_KNOWLEDGE = 4000
BUDGET_QUESTION = 800

MAX_ENTITIES = 3
MAX_GRAPH_DEPTH = 1
MAX_EDGES = 20
MAX_DOCUMENTS = 10
MAX_MEMORY_TURNS = 10


# ── Knowledge Item ──

@dataclass
class KnowledgeItem:
    """A single knowledge context item with embedded provenance.

    Used by DedupService and ContextBuilder for explainability.
    Every item carries its source provenance so the final output
    can attribute each piece of information back to its origin.
    """
    source_type: str        # SOURCES_CHUNK, SOURCES_GRAPH, etc.
    source_id: str          # UUID as string — chunk_id, entity_id, etc.
    entity_type: str        # ENTITY_CLIENT, ENTITY_PROPERTY, etc.
    entity_id: str          # entity UUID as string — for R6 cross-check
    content: str            # text content for the prompt
    score: float = 0.0
    provenance: Provenance = field(default_factory=lambda: Provenance("", "", 0.0))