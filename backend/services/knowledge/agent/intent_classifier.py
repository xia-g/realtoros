"""Intent Classifier — rule-based V1.

Deterministic keyword matching. 100% testable. No LLM calls.
"""

from __future__ import annotations

import re

from backend.services.knowledge.agent.enums import AgentIntent


class IntentClassifier:
    """Классифицирует вопрос пользователя в AgentIntent.

    Правила V1:
    - поиск клиента → SEARCH_CLIENT
    - поиск объекта/недвижимости → SEARCH_PROPERTY
    - поиск сделки → SEARCH_DEAL
    - проверка сделки → CHECK_DEAL
    - документы → VALIDATE_DOCS
    - регламент/нормативный акт → REGULATION_SEARCH
    - аналитика/статистика → CRM_ANALYTICS
    - всё остальное → GENERAL_QA
    """

    def classify(self, question: str) -> AgentIntent:
        """Определить intent по вопросу.

        Приоритет: наиболее специфичные правила проверяются первыми.
        """
        q = question.strip().lower()

        # ── Deal governance (самые специфичные) ──
        if self._match(q, [
            r"провер(?:ить|ьте|ь|яй)\s+(?:сделк|договор)",
            r"(?:состояни[ея]|статус|готовност[ьи])\s+сделк",
            r"насколько\s+сделка\s+(?:готова|соответствует)",
            r"complian[ce]+\s+сделк",
            r"check\s+deal",
        ]):
            return AgentIntent.CHECK_DEAL

        if self._match(q, [
            r"каки[ех]\s+документ",
            r"каки[ех]\s+справ",
            r"документ[ыо]\s+(?:нужны|требуются|необходимы)",
            r"validate\s+(?:document|doc)",
            r"пакет\s+документ",
            r"чего\s+не\s+хватает",
        ]):
            return AgentIntent.VALIDATE_DOCS

        if self._match(q, [
            r"регламент",
            r"нормативн[ыо][йх]\s+акт",
            r"федеральн[ыо][йх]\s+закон",
            r"(?:фз|ФЗ)\b",
            r"минфин|фнс|росреестр|госуслуг[иа]|цб\b",
            r"regulation",
            r"требовани[яе]\s+росреестр",
            r"действующ[и]{1,2}\s+(?:регламент|норм|закон)",
        ]):
            return AgentIntent.REGULATION_SEARCH

        # ── CRM search ──
        if self._match(q, [
            r"(?:най[дт]и|поиск|найти|наше[лд])\s+(?:клиент|покупател)",
            r"кто\s+(?:такой|звонил|писал)",
            r"информаци[яю]\s+о\s+клиент",
            r"(?:search|find)\s+client",
        ]):
            return AgentIntent.SEARCH_CLIENT

        if self._match(q, [
            r"(?:най[дт]и|поиск|найти)\s+(?:объект|недвижимост|квартир|дом|участок|помещени)",
            r"есть\s+ли\s+(?:в\s+продаже|объект|квартир)",
            r"(?:search|find)\s+propert",
        ]):
            return AgentIntent.SEARCH_PROPERTY

        if self._match(q, [
            r"(?:най[дт]и|поиск|найти)\s+(?:сделк|договор)",
            r"(?:search|find)\s+deal",
        ]):
            return AgentIntent.SEARCH_DEAL

        # ── Analytics ──
        if self._match(q, [
            r"(?:аналитик|статистик|отчет|сколько\s+сделок|отчёт)",
            r"analytics|statistics|report",
        ]):
            return AgentIntent.CRM_ANALYTICS

        return AgentIntent.GENERAL_QA

    @staticmethod
    def _match(question: str, patterns: list[str]) -> bool:
        """Проверить вопрос на совпадение с одним из regex-паттернов."""
        for pattern in patterns:
            if re.search(pattern, question):
                return True
        return False
