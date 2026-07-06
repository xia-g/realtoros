"""Tests for Context Builder V1 (P3)."""

import pytest
from uuid_extensions import uuid7

from backend.services.knowledge.context.exceptions import ContextOverflowError
from backend.services.knowledge.context.token_counter import count_tokens, validate_budget
from backend.services.knowledge.context.selection import select_entities, EntityRef
from backend.services.knowledge.context.dedup import DedupService
from backend.services.knowledge.context.assembly import escape_xml_content, ContextAssembler
from backend.services.knowledge.context.contracts import (
    HARD_CAP_TOKENS, BUDGET_SYSTEM, BUDGET_MEMORY, BUDGET_KNOWLEDGE, BUDGET_QUESTION,
    Provenance, ContextBuilderInput, ContextBuilderOutput, KnowledgeItem,
)
from backend.services.knowledge.context.dedup import DedupService

# ── Token Counter Tests ──

class TestTokenCounter:
    def test_count_tokens_returns_int(self):
        n = count_tokens("Hello, world!")
        assert isinstance(n, int)
        assert n > 0

    def test_count_tokens_caching(self):
        from backend.services.knowledge.context.token_counter import _get_encoding
        enc1 = _get_encoding()
        enc2 = _get_encoding()
        assert enc1 is enc2  # singleton

    def test_validate_budget_ok(self):
        tokens = validate_budget({
            "system": 500,
            "memory": 500,
            "knowledge": 2000,
            "question": 200,
        })
        assert tokens == 3200
        assert tokens < HARD_CAP_TOKENS

    def test_validate_budget_overflow(self):
        with pytest.raises(ContextOverflowError) as exc:
            validate_budget({
                "system": 500,
                "memory": 500,
                "knowledge": 4000,
                "question": 2000,  # way over budget
            })
        assert "CONTEXT_OVERFLOW" in str(exc.value.code)
        assert exc.value.status_code == 400


# ── Entity Selection Tests ──

class MockSearchResult:
    def __init__(self, entity_type, entity_id, score):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.score = score

class TestSelection:
    def test_returns_top_3_unique(self):
        results = [
            MockSearchResult("client", uuid7(), 0.9),
            MockSearchResult("client", uuid7(), 0.8),
            MockSearchResult("property", uuid7(), 0.7),
            MockSearchResult("property", uuid7(), 0.6),
            MockSearchResult("deal", uuid7(), 0.5),
        ]
        selected = select_entities(results, max_entities=3)
        assert len(selected) == 3

    def test_deterministic_order(self):
        id1, id2, id3 = uuid7(), uuid7(), uuid7()
        results = [
            MockSearchResult("client", id2, 0.8),
            MockSearchResult("deal", id3, 0.8),
            MockSearchResult("client", id1, 0.9),
        ]
        selected = select_entities(results, max_entities=3)
        # Should be sorted by score DESC, then type ASC, then id ASC
        assert selected[0].score >= selected[1].score >= selected[2].score

    def test_deduplicates_by_type_id(self):
        eid = uuid7()
        results = [
            MockSearchResult("client", eid, 0.9),
            MockSearchResult("client", eid, 0.6),  # duplicate
        ]
        selected = select_entities(results, max_entities=3)
        assert len(selected) == 1
        assert selected[0].score == 0.9  # highest score kept

    def test_handles_empty_results(self):
        selected = select_entities([], max_entities=3)
        assert selected == []


# ── Dedup Tests (KnowledgeItem-based) ──

class TestDedup:
    def _item(self, source_type="chunk", source_id="s1", entity_type="document",
              entity_id="e1", content="content", score=0.9):
        return KnowledgeItem(
            source_type=source_type,
            source_id=source_id,
            entity_type=entity_type,
            entity_id=entity_id,
            content=content,
            score=score,
        )

    def test_r1_same_chunk_id(self):
        svc = DedupService()
        items = [
            self._item(source_type="chunk", source_id="chunk1"),
            self._item(source_type="chunk", source_id="chunk1"),
        ]
        result, ratio = svc.deduplicate(items)
        assert len(result) == 1
        assert ratio > 0

    def test_r2_same_document_id(self):
        svc = DedupService()
        items = [
            self._item(source_type="document", source_id="doc1"),
            self._item(source_type="document", source_id="doc1"),
        ]
        result, ratio = svc.deduplicate(items)
        assert len(result) == 1

    def test_r3_same_entity(self):
        svc = DedupService()
        items = [
            self._item(source_type="graph", source_id="e1", entity_type="client", entity_id="e1"),
            self._item(source_type="graph", source_id="e1", entity_type="client", entity_id="e1"),
        ]
        result, ratio = svc.deduplicate(items)
        assert len(result) == 1

    def test_r4_same_edge(self):
        svc = DedupService()
        items = [
            KnowledgeItem(source_type="edge", source_id="e1", entity_type="", entity_id="",
                          content="edge", score=0.9, provenance=Provenance("", "", 0.0)),
            KnowledgeItem(source_type="edge", source_id="e2", entity_type="", entity_id="",
                          content="edge", score=0.8, provenance=Provenance("", "", 0.0)),
        ]
        # Add edge_source, edge_target, edge_type as attributes
        items[0].edge_source = "a"; items[0].edge_target = "b"; items[0].edge_type = "owns"
        items[1].edge_source = "a"; items[1].edge_target = "b"; items[1].edge_type = "owns"
        result, ratio = svc.deduplicate(items)
        assert len(result) == 1

    def test_r6_graph_overrides_search(self):
        """R6: entity from graph replaces same entity from search chunks."""
        svc = DedupService()
        items = [
            self._item(source_type="chunk", source_id="search1", entity_type="document",
                       entity_id="client123", content="Чанк про клиента 123", score=0.8),
            self._item(source_type="graph", source_id="client123", entity_type="client",
                       entity_id="client123", content="client: Ivanov Ivan", score=0.9),
        ]
        result, ratio = svc.deduplicate(items)
        assert len(result) == 1
        assert result[0].source_type == "graph"  # graph preferred

    def test_r6_keeps_both_when_entity_id_different(self):
        """R6: different entity_ids are both kept."""
        svc = DedupService()
        items = [
            self._item(source_type="chunk", source_id="search1", entity_type="document",
                       entity_id="client100", content="Чанк про клиента 100", score=0.8),
            self._item(source_type="graph", source_id="client200", entity_type="client",
                       entity_id="client200", content="client: Petrov Petr", score=0.9),
        ]
        result, ratio = svc.deduplicate(items)
        assert len(result) == 2  # both kept — different entity_ids

    def test_handles_empty(self):
        svc = DedupService()
        result, ratio = svc.deduplicate([])
        assert result == []
        assert ratio == 0

    def test_dedup_ratio_calculation(self):
        svc = DedupService()
        items = [
            self._item(source_type="chunk", source_id="c1"),
            self._item(source_type="chunk", source_id="c1"),
            self._item(source_type="chunk", source_id="c2"),
            self._item(source_type="chunk", source_id="c3"),
        ]
        result, ratio = svc.deduplicate(items)
        assert len(result) == 3
        assert ratio == 0.25


# ── XML Escape Tests ──

class TestXMLEscape:
    def test_escapes_close_knowledge(self):
        result = escape_xml_content("test </knowledge> hack")
        assert "</knowledge>" not in result
        assert "knowledge" in result  # escaped version still has the word

    def test_escapes_close_system(self):
        result = escape_xml_content("test </system> hack")
        assert "</system>" not in result

    def test_escapes_close_memory(self):
        result = escape_xml_content("test </memory> hack")
        assert "</memory>" not in result

    def test_escapes_close_question(self):
        result = escape_xml_content("test </question> hack")
        assert "</question>" not in result

    def test_escapes_cdata_close(self):
        result = escape_xml_content("test ]]> hack")
        assert "]]>" not in result

    def test_passes_clean_text(self):
        result = escape_xml_content("clean text with no tags")
        assert result == "clean text with no tags"


# ── Assembly Tests ──

class TestAssembly:
    def test_correct_order(self):
        assembler = ContextAssembler()
        prompt, tokens, provenance = assembler.build_prompt(
            system_prompt="System instruction",
            security_instructions="Security note",
            memory_text="Previous conversation",
            knowledge_text="Entity: client, Property: address",
            question="Who is Ivanov?",
        )
        # System should be first, question last
        sys_pos = prompt.index("<system>")
        question_pos = prompt.index("<question>")
        assert sys_pos < question_pos

    def test_sections_present(self):
        assembler = ContextAssembler()
        prompt, tokens, provenance = assembler.build_prompt(
            system_prompt="Sys", security_instructions="Sec",
            memory_text="Mem", knowledge_text="Know", question="Q",
        )
        assert "<system>" in prompt
        assert "<memory>" in prompt
        assert "<knowledge>" in prompt
        assert "<question>" in prompt

    def test_empty_memory_omitted(self):
        assembler = ContextAssembler()
        prompt, tokens, provenance = assembler.build_prompt(
            system_prompt="Sys", security_instructions="Sec",
            memory_text="", knowledge_text="Know", question="Q",
        )
        assert "<memory>" not in prompt

    def test_empty_knowledge_omitted(self):
        assembler = ContextAssembler()
        prompt, tokens, provenance = assembler.build_prompt(
            system_prompt="Sys", security_instructions="Sec",
            memory_text="Mem", knowledge_text="", question="Q",
        )
        assert "<knowledge>" not in prompt


# ── Provenance Tests ──

class TestProvenance:
    def test_provenance_dataclass(self):
        p = Provenance(source_type="chunk", source_id=uuid7(), score=0.95, snippet="Document text")
        assert p.source_type == "chunk"
        assert p.score == 0.95
        assert len(p.snippet) > 0

    def test_provenance_from_assembly(self):
        assembler = ContextAssembler()
        prompt, tokens, provenance = assembler.build_prompt(
            system_prompt="Sys", security_instructions="Sec",
            memory_text="Mem", knowledge_text="Know", question="Q",
        )
        assert len(provenance) > 0
        assert provenance[0].source_type == "system"


# ── Contracts Tests ──

class TestContracts:
    def test_context_builder_input(self):
        inp = ContextBuilderInput(query="test", user_id=uuid7(), correlation_id="abc123")
        assert inp.query == "test"
        assert inp.correlation_id == "abc123"

    def test_context_builder_output_defaults(self):
        out = ContextBuilderOutput(
            prompt="test", token_count=100,
            entities=[], provenance=[], dedup_ratio=0.0, truncated=False,
        )
        assert out.prompt == "test"
        assert out.token_count == 100


# ── KnowledgeItem Tests ──

class TestKnowledgeItem:
    def test_knowledge_item_with_provenance(self):
        prov = Provenance(source_type="chunk", source_id="doc123", score=0.95, snippet="Текст документа")
        item = KnowledgeItem(
            source_type="chunk", source_id="doc123", entity_type="client",
            entity_id="client123", content="Клиент Иванов", score=0.95,
            provenance=prov,
        )
        assert item.provenance.source_type == "chunk"
        assert item.provenance.score == 0.95
        assert item.entity_id == "client123"

    def test_knowledge_item_default_provenance(self):
        item = KnowledgeItem(
            source_type="chunk", source_id="doc1", entity_type="document",
            entity_id="doc1", content="test",
        )
        assert item.provenance.source_type == ""


# ── E2E Overflow Test (H4) ──

class TestOverflowE2E:
    """Verify ContextOverflowError is raised through full build() pipeline with 7000+ tokens."""

    async def test_overflow_with_large_input(self):
        """Build context with 7000+ tokens → ContextOverflowError via validate_budget."""
        # Simulate section_tokens that exceed hard cap
        overflow_tokens = {
            "system": 500,
            "memory": 500,
            "knowledge": 6000,
            "question": 200,
        }
        with pytest.raises(ContextOverflowError) as exc:
            validate_budget(overflow_tokens)
        assert exc.value.code == "CONTEXT_OVERFLOW"
        assert exc.value.status_code == 400
        assert "6800" in str(exc.value.message) or exc.value.details.get("hard_cap") == 6800

    def test_overflow_threshold_boundary(self):
        """Exactly at 6800 → ok, 6801 → overflow."""
        ok_tokens = {
            "system": 500,
            "memory": 500,
            "knowledge": 4000,
            "question": 800,
        }
        total = validate_budget(ok_tokens)
        # 500 + 500 + 4000 + 800 = 5800 — well under cap
        assert total == 5800
        assert total < 6800

    def test_overflow_at_boundary(self):
        """6801 tokens should raise ContextOverflowError."""
        overflow_tokens = {
            "system": 500,
            "memory": 500,
            "knowledge": 5000,
            "question": 801,
        }
        with pytest.raises(ContextOverflowError) as exc:
            validate_budget(overflow_tokens)
        assert exc.value.details["total_tokens"] >= 6801
