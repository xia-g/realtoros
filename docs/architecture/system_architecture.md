# System Architecture

## Layers

```
┌─────────────────────────────────────┐
│          Executive Dashboard         │  Sprint 7B
├─────────────────────────────────────┤
│           Analytics Engine           │  Sprint 7A
├─────────────────────────────────────┤
│        Autonomous Operations         │  Sprint 8
├─────────────────────────────────────┤
│         Deal Operations (6B)         │  Sprint 6B
├─────────────────────────────────────┤
│       Regulatory Intelligence        │  Sprint 6A
├─────────────────────────────────────┤
│          Deal Governance             │  Sprint 5
├─────────────────────────────────────┤
│      Knowledge Graph + Memory        │  Sprint 4
├─────────────────────────────────────┤
│      Security Layer (P5)             │  Sprint 4
├─────────────────────────────────────┤
│            Agent Runtime             │  Sprint 3
├─────────────────────────────────────┤
│         Service Layer                │  Sprint 2
├─────────────────────────────────────┤
│   Domain Model (SQLAlchemy 2)        │  Sprint 1
├─────────────────────────────────────┤
│   PostgreSQL 17 (88 tables, 72 part) │
└─────────────────────────────────────┘
```

## Data Flow

```
Client → API (:8090) → Service → Repository → DB
                                  ↕
                            DomainEventBus
                                  ↕
                 ┌────────────────┼────────────┐
                 ↓                ↓            ↓
         Knowledge Graph    Embeddings    Compliance
```

## Partition Strategy

- `ai_call_log` — RANGE (created_at), monthly
- `agent_tool_calls` — RANGE (created_at), monthly
- `compliance_audits` — RANGE (created_at), monthly

## Subdomains (Sprint UI-1)

- `crm.spcnn.ru` — CRM, Deals, Documents, Knowledge, Copilot, Operations
- `executive.spcnn.ru` — KPI, War Rooms, Recommendations
- `analytics.spcnn.ru` — Business, Funnel, Portfolio, Predictions
- `admin.spcnn.ru` — Settings, Users, AI, MCP, Monitoring, Partitions
- `api.spcnn.ru` — All REST endpoints

## Multi-Tenant

All domains via `DomainConfigService` + `platform_settings` table.
Zero hardcoded domains. Any `primary_domain` works.

## Key Ports

| Service | Port |
|---------|------|
| Backend API | 8090 |
| Frontend | 3000 |
| MCP Server | stdio |
| PostgreSQL | 5432 |
