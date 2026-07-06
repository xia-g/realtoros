# Generated Services

| Service | File | Methods |
|--------|------|---------|
| Priority | backend/services/autonomous_services.py | __init__, _priority, generate_tasks, generate_from_compliance, generate_from_sla_breach |
| HealthLevel | backend/services/autonomous_services.py | __init__, _priority, generate_tasks, generate_from_compliance, generate_from_sla_breach |
| ClientService | backend/services/client.py | __init__, repo, search_by_phone, search_by_telegram |
| DealService | backend/services/deal.py | __init__, repo, get_with_participants, get_by_client |
| AgentIntent | backend/services/knowledge/agent/enums.py |  |
| SourceType | backend/services/knowledge/agent/enums.py |  |
| ContextOverflowError | backend/services/knowledge/context/exceptions.py | __init__, __init__ |
| ContextBuildError | backend/services/knowledge/context/exceptions.py | __init__, __init__ |
| KnowledgeSourceType | backend/services/knowledge/security/enums.py | for_source, score, from_finding_count |
| KnowledgeTrustLevel | backend/services/knowledge/security/enums.py | for_source, score, from_finding_count |
| SecuritySeverity | backend/services/knowledge/security/enums.py | for_source, score, from_finding_count |
| PatternDef | backend/services/knowledge/security/patterns.py | _c |
| PropertyService | backend/services/property.py | __init__, repo, get_by_owner, get_available |