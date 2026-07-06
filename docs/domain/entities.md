# Domain Entities

## Core Entities

- **User** — employees, agents, admins. Role-based (Executive, Admin, Broker, Realtor, Lawyer, Compliance, Accountant, Viewer)
- **Client** — buyer/seller. Source: referral, site, telegram, call, other, lead_conversion
- **Property** — real estate object. Type: apartment, house, commercial, land
- **Deal** — transaction between parties. Stages: initiated→verification→mortgage→registration→closing
- **Document** — uploaded files linked to deals/clients. Types: passport, egrn, purchase_agreement, mortgage_contract, etc.

## Deal Lifecycle (Sprint 5)

- Deal → ComplianceAudit → Regulation → RegulationVersion
- Deal → DealTimelineEvent (history)
- Deal → DealHealthSnapshot (health_score, compliance_score, risk_score)
- Deal → DocumentPackage (required documents per deal type)

## Knowledge & AI (Sprint 4)

- KnowledgeGraphNode → KnowledgeGraphEdge (relationships)
- PageChunk → ChunkEmbedding (vector search)
- ai_call_log — partitioned by month
- agent_tool_calls — partitioned by month

## Operations (Sprint 6B, 8)

- DealPlaybook → DealPlaybookCheckpoint → CheckpointVerification
- DealAction → ActionAssignment
- DealSLA → SLAViolation
- Escalation → EscalationAction

## Analytics (Sprint 7A, 7B)

- AnalyticsSnapshot → AnalyticsAlert
- PredictionResult
- BusinessMetric → FunnelStage

## Database

- 88 tables, 36 data partitions, 36 index partitions
- 25 applied migrations
- CHECK constraints on all score/status columns
- Soft delete (deleted_at) on all domain entities
