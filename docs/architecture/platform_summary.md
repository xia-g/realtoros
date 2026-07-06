# Real Estate OS — Архитектурный Summary

**Дата:** 2026-06-09
**Источник:** MCP + filesystem
**Всего:** 23,402 строк Python, 116 документов

---

## Сравнение MCP vs Реальность

| Аспект | MCP знает | Реальность | Расхождение |
|--------|-----------|------------|-------------|
| Модели | Нет | 46 файлов, 49 классов | MCP не имеет доступа к моделям |
| Миграции | Нет | 21 | MCP не отслеживает |
| Тесты | Нет | 669 тестов, 36 файлов | MCP не отслеживает |
| API эндпоинты | Нет | 101 | MCP не отслеживает |
| Сервисы | Нет | 57 service классов | MCP не отслеживает |
| Инструменты | 20 (через @mcp.tool) | 20 | ✅ Совпадает |
| Vision | ✅ vision.md | ✅ | ✅ |
| Architecture | ✅ system_architecture.md | ✅ | ✅ |
| Entities | ✅ entities.md | ✅ | ✅ |
| Roadmap | ✅ roadmap/mvp.md | ✅ | ✅ |
| Status | ✅ project_status.md | ⚠️ Устарел | MCP не видел Sprint 4-8 обновления |
| Skills | ✅ docs/skills/ | ✅ | ✅ |
| Backlog | ✅ backlog.json | ✅ | ✅ |

**MCP-сервер синхронизирован с docs/ директорией, но не имеет доступа к backend-коду.**

---

## 1. Sprint Progress (12 спринтов завершено)

```
Sprint 1-2:    CRM Foundation             ✅
Sprint 1B:     Runtime Foundation          ✅
Sprint 2.5:    API Gap Closure             ✅
Sprint 3A:     Knowledge Foundation        ✅
Sprint 4:      Knowledge Agent Runtime     ✅
Sprint 5:      Deal Lifecycle Compliance   ✅
Sprint 5.2:    Critical Architecture Fixes ✅
Sprint 6A:     Regulatory Intelligence     ✅
Sprint 6B:     Deal Operations Platform    ✅
Sprint 7A:     Analytics & Decision Intel  ✅
Sprint 7B:     Executive Dashboard         ✅
Sprint 8:      Autonomous Operations       ✅
```

---

## 2. Models (49 классов, 46 файлов)

### CRM Core (10)
`User`, `Role`, `Client`, `ClientContact`, `Property`, `Deal`, `DealParticipant`, `Document`, `Communication`, `Task`

### Lead Management (2)
`Lead`, `LeadEvent`

### Workflow & Compliance (9)
`DealWorkflow`, `DealStageTransition`, `DealCheckpoint`, `DealSLA`, `DealAction`, `DealHealthSnapshot`, `DealRiskAssessment`, `DealDocumentPackage`, `DocumentRequirement`

### Playbook & Timeline (3)
`DealPlaybook`, `DealPlaybookStage`, `DealPlaybookCheckpoint`, `DealTimelineEvent`

### Knowledge (7)
`DocumentChunk`, `Embedding`, `GraphNode`, `GraphEdge`, `KnowledgeSession`, `KnowledgeMessage`, `AIQueryLog`

### Regulation (7)
`Regulation`, `RegulationVersion`, `RegulationSyncJob`, `RegulationSource`, `RegulationChangeEvent`, `RegulationSyncLog`, `RegulationImpact`, `RegulationRequirementMapping`

### Audit (5)
`ComplianceAudit`, `DealOperationsAudit`, `AgentToolCall`, `AnalyticsSnapshot`, `AnalyticsAlert`

### Operations (3)
`BudgetUsage`, `Notification`, `SystemJob`, `PredictionResult`

### Other (2)
`Stakeholder`, `DocumentValidation`

---

## 3. Services (57 классов)

| Группа | Сервисы | Ключевая функциональность |
|--------|---------|---------------------------|
| **CRM** | ClientService, DealService, PropertyService, TaskService, CommunicationService, LeadService | CRUD, конверсия лидов, поиск |
| **Workflow** | WorkflowService, PlaybookService, SLAService, TimelineService | Жизненный цикл сделки, SLA, таймлайн |
| **Compliance** | ComplianceService, DocumentPackageService, DocumentValidationService | Compliance score, комплектность документов |
| **Risk** | RiskAssessmentService, OperationalHealthService | 8 факторов риска, операционное здоровье |
| **Regulation** | RegulationService, RegulationSourceService, RegulationSyncServiceV2, RegulationParserService, RegulationDiffService, RegulationImpactServiceV2 | Регламенты, версионирование, diff, анализ |
| **Agent** | AgentRuntime, IntentClassifier, ToolPlanner, ToolRegistry, ToolExecutor | AI Agent pipeline |
| **Context** | ContextBuilder, TokenCounter, SelectionService, DedupService, GraphExpansionService | Контекст для LLM |
| **Memory** | MemoryService, CleanupService | Сессии, 24h TTL |
| **Security** | Detector, Sanitizer, XMLDetector, IntegrationService | Prompt injection, XML escaping |
| **Cost** | CostTracker, AIAuditService, AgentToolAuditService | Бюджет, аудит вызовов |
| **Analytics** | BusinessMetricsService, FunnelAnalyticsService, TeamPerformanceService, PortfolioAnalyticsService, PredictionEngine, AlertEngine | BI, предиктивы, алерты |
| **Executive** | ExecutiveDashboardService, OperationsCenterService, WarRoomService, ExecutiveCopilot, TelegramExecutiveAssistant | Дашборд, command center |
| **Autonomous** | TaskOrchestrator, AssignmentService, EscalationService, DealRecoveryEngine, ActionRecommendationService, ExecutiveActionCenter | Автономные операции |
| **Graph** | GraphLifecycleService | Синхронизация графа |
| **Events** | DomainEventBus (core), EventHandlers | Шина событий |

---

## 4. API (101 endpoint, 10 routers)

| Router | Endpoints | Примеры |
|--------|-----------|---------|
| `leads.py` | 11 | CRUD, assign, close |
| `tasks.py` | 8 | CRUD, status |
| `system_jobs.py` | 8 | Scheduler |
| `documents.py` | 4 | Upload, list |
| `knowledge.py` | 6 | Search, graph |
| `agent.py` | 3 | POST /ask, GET /tools |
| `sprint5.py` | 12 | Workflow, compliance, risk, regulations |
| `sprint6a.py` | 6 | Sync, changes, impact |
| `sprint6b.py` | 17 | Playbooks, SLA, stakeholders, health, actions, copilot |
| `sprint7a.py` | 9 | Dashboard, funnel, team, portfolio, predictions, alerts |
| `sprint7b.py` | 14 | Executive dashboard, war rooms, approvals |
| `sprint8.py` | 14 | Tasks, assignments, escalations, recovery, approvals |

---

## 5. MCP Tools (20)

| Tool | Source | Purpose |
|------|--------|---------|
| `search_project` | project_tools | Полнотекстовый поиск по docs/ |
| `project_vision` | project_tools | Видение проекта |
| `project_architecture` | project_tools | Архитектура |
| `project_entities` | project_tools | Доменные сущности |
| `project_roadmap` | project_tools | Roadmap |
| `project_status` | project_tools | Статус (устарел — не видел Sprint 4-8) |
| `development_rules` | project_tools | Правила разработки |
| `all_skills` | project_tools | Все навыки |
| `project_context` | project_tools | Всё сразу |
| `create_task` | project_tools | Создать задачу в backlog |
| `list_tasks` | project_tools | Список задач |
| `update_task` | project_tools | Обновить статус |
| `update_project_status` | project_tools | Обновить project_status.md |
| `check_deal_completeness` | deal_tools | Compliance score сделки |
| `validate_document_package` | deal_tools | Проверка документов |
| `get_regulation` | deal_tools | Поиск регламентов |
| `check_deal_status` | deal_tools | Статус + compliance + risk |
| `check_deal_risks` | deal_tools | Оценка рисков |
| `get_regulation_updates` | deal_tools | Обновления регламентов |
| `get_next_actions` | deal_tools | Следующие шаги |

---

## 6. Infrastructure

| Компонент | Параметр | Значение |
|-----------|----------|----------|
| Python | LOC | 23,402 |
| Тесты | Всего | **669** (36 файлов) |
| Миграции | Всего | **21** |
| Индексы | Всего | **154** |
| ADR | Всего | **16** |
| Спринт доки | Всего | **22** |
| MCP инструменты | Всего | **20** |
| API эндпоинты | Всего | **101** |
| Сервисы | Классов | **57** |
| Модели | Таблиц | **39** |

---

## 7. Архитектурные решения

```
Слой изоляции:     API → Services → Repositories → Models
Шина событий:      DomainEventBus (16 типов, но 13 не эмитятся)
AI Pipeline:       Intent → Plan → Tools → Context → LLM → Answer
Approval Gate:     Все autonomous actions требуют human approve
Soft Delete:       ✅ На всех доменных таблицах (после Sprint 5.2)
Correlation ID:    ✅ Сквозной через audit_events → ai_call_log → agent_tool_calls
Rate Limiting:     ✅ PostgreSQL advisory lock + in-memory fallback
Partitioning:      ⚠️ Только комментарии, реальные partition не созданы
Knowledge Sync:    ❌ CRM→Graph не подключен (event_handlers не импортирован)
```

---

## 8. Состояние MCP-сервера

MCP-сервер работает как FastMCP на 20 инструментов. Он:
- Читает docs/ (vision, architecture, entities, roadmap, status)
- Управляет backlog через backlog.json
- Предоставляет deal governance инструменты (compliance, risk, regulation)
- Не имеет доступа к backend-коду
- project_status.md устарел (не отражает Sprint 4-8)
- Не подключён к Hermes Agent (не зарегистрирован в config.yaml)

---

## 9. Ключевые метрики

| Метрика | Значение |
|---------|----------|
| Production Readiness | 99/100 (feat) / 84/100 (arch) |
| Всего тестов | 669 |
| Всего эндпоинтов | 101 |
| Всего MCP инструментов | 20 |
| Всего миграций | 21 |
| Всего ADR | 16 |
| Всего документов | 116 |
| Спринтов завершено | 12 |
