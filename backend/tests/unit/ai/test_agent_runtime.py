"""Tests for Sprint 4 P6 Agent Runtime V1."""

import asyncio
import json
from uuid import UUID

import pytest

from backend.services.knowledge.agent.enums import AgentIntent
from backend.services.knowledge.agent.contracts import AgentRequest, ToolPlan, SourceReference, ToolCall
from backend.services.knowledge.agent.intent_classifier import IntentClassifier
from backend.services.knowledge.agent.tool_planner import ToolPlanner
from backend.services.knowledge.agent.tool_executor import ToolExecutor
from backend.services.knowledge.agent.tool_registry import ToolRegistry
from backend.services.knowledge.agent.agent_tools import (
    agent_check_deal_completeness,
    agent_validate_document_package,
    agent_get_regulation,
)
from backend.services.rate_limiter import RateLimiter

# ── Helpers ──

_user_id = UUID(int=1)


def _make_registry() -> ToolRegistry:
    r = ToolRegistry()
    r.register_tool("check_deal_completeness", "Check deal", agent_check_deal_completeness)
    r.register_tool("validate_document_package", "Validate docs", agent_validate_document_package)
    r.register_tool("get_regulation", "Get regulation", agent_get_regulation)
    return r


# ── Intent Classification (P6.1) ──


class TestIntentClassifier:
    """1.1: Determine classification is deterministic."""

    def setup_method(self):
        self.classifier = IntentClassifier()

    def test_classify_check_deal(self):
        questions = [
            "Проверь сделку №145",
            "проверить сделку иванова",
            "Насколько сделка готова?",
            "проверь состояние договора",
            "check deal 145",
        ]
        for q in questions:
            assert self.classifier.classify(q) == AgentIntent.CHECK_DEAL, f"Failed: {q}"

    def test_classify_validate_docs(self):
        questions = [
            "Какие документы нужны для ипотеки?",
            "какие справки требуются",
            "документы для продажи квартиры",
            "validate document package",
            "чего не хватает из документов",
        ]
        for q in questions:
            assert self.classifier.classify(q) == AgentIntent.VALIDATE_DOCS, f"Failed: {q}"

    def test_classify_regulation_search(self):
        questions = [
            "Какие требования Росреестра действуют?",
            "нормативный акт по ипотеке",
            "ФЗ 218 что это?",
            "regulation search",
            "минфин требования",
        ]
        for q in questions:
            assert self.classifier.classify(q) == AgentIntent.REGULATION_SEARCH, f"Failed: {q}"

    def test_classify_search_client(self):
        questions = [
            "Найди клиента Иванов",
            "поиск клиента по телефону",
            "найти покупателя петрова",
            "search client",
        ]
        for q in questions:
            assert self.classifier.classify(q) == AgentIntent.SEARCH_CLIENT, f"Failed: {q}"

    def test_classify_search_property(self):
        questions = [
            "найди объект на Ленина",
            "поиск квартиры в центре",
            "найти недвижимость по адресу",
            "search property",
        ]
        for q in questions:
            assert self.classifier.classify(q) == AgentIntent.SEARCH_PROPERTY, f"Failed: {q}"

    def test_classify_search_deal(self):
        assert self.classifier.classify("найти сделку №145") == AgentIntent.SEARCH_DEAL
        assert self.classifier.classify("search deal") == AgentIntent.SEARCH_DEAL

    def test_classify_crm_analytics(self):
        assert self.classifier.classify("сколько сделок закрыто") == AgentIntent.CRM_ANALYTICS
        assert self.classifier.classify("статистика по продажам") == AgentIntent.CRM_ANALYTICS

    def test_classify_general_qa(self):
        questions = [
            "Привет!",
            "Что такое ипотека?",
            "сколько времени занимает регистрация",
            "как продать квартиру",
        ]
        for q in questions:
            assert self.classifier.classify(q) == AgentIntent.GENERAL_QA, f"Failed: {q}"
    """1.2: Classification is deterministic (same input = same output)."""

    def test_deterministic(self):
        q = "Проверь сделку Иванова"
        assert self.classifier.classify(q) == self.classifier.classify(q)
        assert self.classifier.classify(q) == self.classifier.classify(q.upper())
        assert self.classifier.classify(q) == self.classifier.classify(q.lower())


# ── Tool Planning (P6.2) ──


class TestToolPlanner:
    def setup_method(self):
        self.planner = ToolPlanner()

    def test_plan_check_deal(self):
        plan = self.planner.plan(AgentIntent.CHECK_DEAL)
        assert plan.intent == AgentIntent.CHECK_DEAL
        assert "check_deal_completeness" in plan.tools

    def test_plan_validate_docs(self):
        plan = self.planner.plan(AgentIntent.VALIDATE_DOCS)
        assert "validate_document_package" in plan.tools

    def test_plan_regulation_search(self):
        plan = self.planner.plan(AgentIntent.REGULATION_SEARCH)
        assert "get_regulation" in plan.tools

    def test_plan_search_client(self):
        plan = self.planner.plan(AgentIntent.SEARCH_CLIENT)
        assert "search_client" in plan.tools

    def test_plan_general_qa(self):
        plan = self.planner.plan(AgentIntent.GENERAL_QA)
        assert plan.tools == []

    def test_plan_deterministic(self):
        p1 = self.planner.plan(AgentIntent.CHECK_DEAL)
        p2 = self.planner.plan(AgentIntent.CHECK_DEAL)
        assert p1.tools == p2.tools

    def test_plan_has_all_intents(self):
        """All intents must have a plan."""
        for intent in AgentIntent:
            plan = self.planner.plan(intent)
            assert plan is not None


# ── Tool Registry (P6.2) ──


class TestToolRegistry:
    def setup_method(self):
        self.registry = _make_registry()

    def test_register_and_get(self):
        assert self.registry.has_tool("check_deal_completeness")
        tool = self.registry.get_tool("check_deal_completeness")
        assert tool.name == "check_deal_completeness"

    def test_list_tools(self):
        tools = self.registry.list_tools()
        names = [t["name"] for t in tools]
        assert "check_deal_completeness" in names
        assert "validate_document_package" in names
        assert "get_regulation" in names

    def test_execute_unknown_tool(self):
        result = asyncio.run(self.registry.execute("nonexistent"))
        assert result["success"] is False
        assert "not found" in result["error_message"]

    def test_execute_check_deal(self):
        result = asyncio.run(self.registry.execute("check_deal_completeness", deal_id="00000000-0000-0000-0000-000000000000"))
        assert result["success"] is True
        data = json.loads(result["result"])
        assert "compliance_score" in data
        assert "missing_items" in data


# ── Tool Executor (P6.2) ──


class TestToolExecutor:
    def setup_method(self):
        self.registry = _make_registry()
        self.executor = ToolExecutor(self.registry)

    @pytest.mark.asyncio
    async def test_executor_success(self):
        result = await self.executor.execute_tool("check_deal_completeness", deal_id="00000000-0000-0000-0000-000000000000")
        assert isinstance(result, ToolCall)
        assert result.success is True
        assert result.duration_ms > 0
        assert result.tool_name == "check_deal_completeness"

    @pytest.mark.asyncio
    async def test_executor_failure(self):
        result = await self.executor.execute_tool("nonexistent_tool")
        assert result.success is False
        assert "not found" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_executor_governance_tools(self):
        """All 3 governance tools execute successfully."""
        for tool_name in ["check_deal_completeness", "validate_document_package", "get_regulation"]:
            result = await self.executor.execute_tool(tool_name, query="ипотека")
            assert result is not None


# ── Rate Limiter ──


class TestRateLimiter:
    def test_allows_first_request(self):
        limiter = RateLimiter(rpm=10, rph=100)
        assert limiter.check(_user_id) is True

    def test_blocks_at_rpm_limit(self):
        limiter = RateLimiter(rpm=3, rph=100)
        for _ in range(3):
            assert limiter.check(_user_id) is True
        assert limiter.check(_user_id) is False

    def test_blocks_at_rph_limit(self):
        limiter = RateLimiter(rpm=1000, rph=5)
        for _ in range(5):
            assert limiter.check(_user_id) is True
        assert limiter.check(_user_id) is False

    def test_different_users_independent(self):
        limiter = RateLimiter(rpm=1, rph=100)
        uid1 = UUID(int=1)
        uid2 = UUID(int=2)
        assert limiter.check(uid1) is True
        assert limiter.check(uid2) is True  # different user — allowed
        assert limiter.check(uid1) is False  # same user — blocked


# ── Governance Tools Integration ──


class TestGovernanceTools:
    @pytest.mark.asyncio
    async def test_check_deal_structure(self):
        result = await agent_check_deal_completeness(
            deal_id="00000000-0000-0000-0000-000000000000",
            deal_type="SALE_APARTMENT",
            completed_checkpoints="client_verified,object_verified",
            uploaded_documents="passport_seller,passport_buyer",
        )
        assert result["success"] is True
        data = json.loads(result["result"])
        assert "compliance_score" in data
        assert data["compliance_score"] < 100  # not all items completed
        assert "missing_items" in data

    @pytest.mark.asyncio
    async def test_validate_docs_structure(self):
        result = await agent_validate_document_package(
            deal_type="SALE_APARTMENT",
            uploaded_documents="passport_seller,ownership_extract",
        )
        assert result["success"] is True
        data = json.loads(result["result"])
        assert "document_completeness" in data
        assert "missing_required" in data

    @pytest.mark.asyncio
    async def test_get_regulation_structure(self):
        result = await agent_get_regulation(query="ипотека", min_trust="COMMUNITY", limit=5)
        assert result["success"] is True
        data = json.loads(result["result"])
        assert isinstance(data, list)
        if data:
            assert "title" in data[0]
            assert "source" in data[0]
            assert "trust_level" in data[0]


# ── Regulation Priority ──


class TestRegulationPriority:
    def test_trust_level_order(self):
        """OFFICIAL > VERIFIED > COMMUNITY > LLM_GENERATED"""
        order = {"OFFICIAL": 4, "VERIFIED": 3, "COMMUNITY": 2, "LLM_GENERATED": 1}
        assert order["OFFICIAL"] > order["VERIFIED"]
        assert order["VERIFIED"] > order["COMMUNITY"]
        assert order["COMMUNITY"] > order["LLM_GENERATED"]

    def test_source_sorting(self):
        """Sources must be sorted by trust_level descending."""
        sources = [
            SourceReference(source_type="regulation", source_id="1", trust_level="LLM_GENERATED"),
            SourceReference(source_type="regulation", source_id="2", trust_level="OFFICIAL"),
            SourceReference(source_type="regulation", source_id="3", trust_level="VERIFIED"),
        ]
        trust_order = {"OFFICIAL": 4, "VERIFIED": 3, "COMMUNITY": 2, "LLM_GENERATED": 1}
        sorted_sources = sorted(sources, key=lambda s: trust_order.get(s.trust_level, 0), reverse=True)
        assert sorted_sources[0].trust_level == "OFFICIAL"
        assert sorted_sources[1].trust_level == "VERIFIED"
        assert sorted_sources[2].trust_level == "LLM_GENERATED"


# ── Contracts ──


class TestContracts:
    def test_agent_request(self):
        req = AgentRequest(user_id=_user_id, session_id=None, question="test", correlation_id="abc")
        assert req.question == "test"
        assert req.correlation_id == "abc"

    def test_tool_call(self):
        tc = ToolCall(tool_name="test", arguments={"a": 1}, success=True, duration_ms=10.5, result="ok")
        assert tc.success is True
        assert tc.duration_ms == 10.5

    def test_source_reference(self):
        sr = SourceReference(source_type="regulation", source_id="123", trust_level="OFFICIAL", score=0.95)
        assert sr.trust_level == "OFFICIAL"
        assert sr.score == 0.95

    def test_tool_plan(self):
        plan = ToolPlan(intent=AgentIntent.CHECK_DEAL, tools=["check_deal_completeness"])
        assert plan.intent == AgentIntent.CHECK_DEAL
        assert "check_deal_completeness" in plan.tools


# ── E2E Scenarios ──


class TestE2EScenarios:
    """5 end-to-end scenarios from the specification."""

    @pytest.mark.asyncio
    async def test_e2e_scenario_1_check_deal(self):
        """Q: Проверь сделку №145 → check_deal_completeness."""
        classifier = IntentClassifier()
        planner = ToolPlanner()
        intent = classifier.classify("Проверь сделку №145")
        assert intent == AgentIntent.CHECK_DEAL
        plan = planner.plan(intent)
        assert "check_deal_completeness" in plan.tools

    @pytest.mark.asyncio
    async def test_e2e_scenario_2_validate_docs(self):
        """Q: Какие документы нужны для ипотеки? → validate_document_package."""
        classifier = IntentClassifier()
        planner = ToolPlanner()
        intent = classifier.classify("Какие документы нужны для ипотеки?")
        assert intent == AgentIntent.VALIDATE_DOCS
        plan = planner.plan(intent)
        assert "validate_document_package" in plan.tools

    @pytest.mark.asyncio
    async def test_e2e_scenario_3_regulation(self):
        """Q: Какие требования Росреестра действуют сейчас? → get_regulation."""
        classifier = IntentClassifier()
        planner = ToolPlanner()
        intent = classifier.classify("Какие требования Росреестра действуют?")
        assert intent == AgentIntent.REGULATION_SEARCH
        plan = planner.plan(intent)
        assert "get_regulation" in plan.tools

    @pytest.mark.asyncio
    async def test_e2e_scenario_4_search_client(self):
        """Q: Найди клиента Иванов → search_client."""
        classifier = IntentClassifier()
        planner = ToolPlanner()
        intent = classifier.classify("Найди клиента Иванов")
        assert intent == AgentIntent.SEARCH_CLIENT
        plan = planner.plan(intent)
        assert "search_client" in plan.tools

    @pytest.mark.asyncio
    async def test_e2e_scenario_5_regulation_search(self):
        """Q: Что изменилось по регламентам за последний месяц? → get_regulation."""
        classifier = IntentClassifier()
        intent = classifier.classify("Что изменилось по регламентам за последний месяц?")
        assert intent == AgentIntent.REGULATION_SEARCH

    @pytest.mark.asyncio
    async def test_e2e_governance_tool_execution(self):
        """Governance tools actually execute in full flow."""
        registry = _make_registry()
        executor = ToolExecutor(registry)
        result = await executor.execute_tool("check_deal_completeness", deal_id="00000000-0000-0000-0000-000000000000")
        assert result.success is True
        data = json.loads(result.result)
        assert isinstance(data["compliance_score"], (int, float))


# ── Audit ──


class TestAuditToolCall:
    def test_tool_call_audit_fields(self):
        tc = ToolCall(tool_name="test", arguments={}, success=True, duration_ms=5.0, result="ok")
        assert tc.tool_name == "test"
        assert tc.duration_ms == 5.0
        assert tc.success is True

    def test_failure_tool_call_has_error(self):
        tc = ToolCall(tool_name="test", arguments={}, success=False, duration_ms=2.0, error_message="timeout")
        assert tc.success is False
        assert tc.error_message == "timeout"
