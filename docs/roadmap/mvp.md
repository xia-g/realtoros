# Roadmap — MVP to Production

## Completed ✅

### Sprint 1 — Domain Model
Users, Clients, Properties, Deals, Documents, Leads, Tasks, Roles

### Sprint 2 — Service Layer
CRUD + business logic services for all entities

### Sprint 3 — Agent Runtime + Knowledge
FastMCP server, Knowledge Graph, Embeddings, Context Builder

### Sprint 4 — Memory + Security (P4, P5, P6)
Memory Layer, Security Layer, Agent Runtime

### Sprint 5 — Deal Lifecycle + Governance
Compliance Engine, Risk Engine, Deal Governance, Document Requirements

### Sprint 6A — Regulatory Intelligence
Rosreestr/FNS/CBR adapters, RegulationParser, RegulationDiff

### Sprint 6B — Deal Operations
Playbooks, SLA, Timeline, Stakeholders, Document Validation, Deal Health

### Sprint 7A — Analytics
Business Metrics, Funnel, Team Performance, Portfolio, Predictions

### Sprint 7B — Executive Dashboard
KPI, War Rooms, Executive AI Copilot, Telegram Assistant

### Sprint 8 — Autonomous Operations
Task Orchestrator, Assignment, Escalation, Deal Recovery, Executive Actions

### Sprint 8.5-8.8 — Production Hardening
Architecture review, real event emission, partitioning, CHECK constraints, FK fixes, Agent budgets, 25 adversarial tests

### Sprint UI-1 — Platform Configuration
PlatformSettings, DomainConfigService, 180 URL routes, NGINX config, RBAC matrix

### Sprint UI-2 — Operations Console
Next.js 15 frontend: CRM, Deal Workspace, Documents, AI Copilot, Admin Console

## Current

**Sprint UI-2 finalized** — frontend production build at :3000, backend at :8090.

## Next

- Deployment to production
- User acceptance testing on 100 clients / 50 properties / 30 deals
- Performance tuning under load
