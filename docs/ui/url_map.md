# Sprint UI-1 — Full URL Map (180 routes)

**Subdomain Layout:**
- `crm.spcnn.ru` — CRM + Deals + Documents + Operations
- `admin.spcnn.ru` — System settings + Monitoring
- `executive.spcnn.ru` — KPI + War Rooms
- `analytics.spcnn.ru` — Reports + Predictions
- `api.spcnn.ru` — REST API

---

# CRM Subdomain (`crm.spcnn.ru`)

## Auth (8)
```
GET    /login                         # Login page
POST   /login                         # Login action
GET    /logout                        # Logout
GET    /profile                       # Profile
PUT    /profile                       # Update profile
GET    /password/change               # Change password
POST   /password/change               # Password change action
GET    /password/reset                # Password reset
```

## Dashboard (3)
```
GET    /                              # Main dashboard
GET    /dashboard                     # Dashboard (aliased)
GET    /dashboard/tasks               # My tasks widget
```

## Clients (8)
```
GET    /clients                       # Client list
GET    /clients/new                   # New client form
POST   /clients                       # Create client
GET    /client/{id}                   # Client detail
PUT    /client/{id}                   # Update client
DELETE /client/{id}                   # Delete client
GET    /client/{id}/deals             # Client deals
GET    /client/{id}/documents         # Client documents
```

## Properties (8)
```
GET    /properties                    # Property list
GET    /properties/new                # New property form
POST   /properties                    # Create property
GET    /property/{id}                 # Property detail
PUT    /property/{id}                 # Update property
DELETE /property/{id}                 # Delete property
GET    /property/{id}/deals           # Property deals
GET    /property/{id}/documents       # Property documents
```

## Leads (12)
```
GET    /leads                         # Lead list
GET    /leads/new                     # New lead form
POST   /leads                         # Create lead
GET    /lead/{id}                     # Lead detail
PUT    /lead/{id}                     # Update lead
DELETE /lead/{id}                     # Delete lead
POST   /lead/{id}/convert             # Convert lead to client
POST   /lead/{id}/qualify             # Qualify lead
POST   /lead/{id}/score               # Score lead
POST   /lead/{id}/merge               # Merge lead
GET    /lead/{id}/events              # Lead event history
GET    /lead/{id}/timeline            # Lead timeline
```

## Deals (15)
```
GET    /deals                         # Deal list
GET    /deals/new                     # New deal form
POST   /deals                         # Create deal
GET    /deal/{id}                     # Deal workspace (main)
GET    /deal/{id}/overview            # Deal overview tab
GET    /deal/{id}/participants        # Participants tab
GET    /deal/{id}/documents           # Documents tab
GET    /deal/{id}/workflow            # Workflow tab
GET    /deal/{id}/compliance          # Compliance tab
GET    /deal/{id}/risks               # Risks tab
GET    /deal/{id}/timeline            # Timeline tab
GET    /deal/{id}/operations          # Operations tab
GET    /deal/{id}/ai                  # AI Copilot tab
GET    /deal/{id}/audit               # Audit tab
PUT    /deal/{id}                     # Update deal
```

## Documents (12)
```
GET    /documents                     # Document center
GET    /documents/upload              # Upload form
POST   /documents                     # Upload document
GET    /document/{id}                 # Document detail
PUT    /document/{id}                 # Update document
DELETE /document/{id}                 # Delete document
GET    /document/{id}/versions        # Document versions
POST   /document/{id}/validate        # Validate document
GET    /document/{id}/compliance      # Compliance check
GET    /document/{id}/requirements    # Required docs
GET    /document-packages             # Package list
GET    /document-package/{id}         # Package detail
```

## Compliance (10)
```
GET    /compliance                    # Compliance center
GET    /compliance/readiness          # Readiness dashboard
GET    /compliance/violations         # Violations list
GET    /compliance/checkpoints        # Checkpoint list
GET    /compliance/checkpoint/{id}    # Checkpoint detail
GET    /compliance/regulations        # Active regulations
GET    /compliance/affected-deals    # Deals affected by regulations
GET    /compliance/audit/{id}         # Audit record detail
GET    /compliance/report             # Compliance report
GET    /compliance/history            # Compliance history
```

## Operations (12)
```
GET    /operations                    # Operations center
GET    /operations/sla                # SLA dashboard
GET    /operations/playbooks          # Playbook list
GET    /operations/playbook/{id}      # Playbook detail
GET    /operations/actions            # Action list
GET    /operations/action/{id}        # Action detail
POST   /operations/action/{id}/approve     # Approve action
POST   /operations/action/{id}/reject      # Reject action
GET    /operations/stakeholders       # Stakeholder list
GET    /operations/health             # Deal health dashboard
GET    /operations/escalations        # Escalation list
GET    /operations/recovery-plans     # Recovery plans
```

## Knowledge (8)
```
GET    /knowledge                     # Knowledge center
GET    /knowledge/graph               # Knowledge graph view
GET    /knowledge/entities            # Entity list
GET    /knowledge/chunks              # Document chunks
GET    /knowledge/search              # Knowledge search
GET    /knowledge/memory              # Memory sessions
GET    /knowledge/session/{id}        # Session detail
GET    /knowledge/context             # Context builder
```

## AI (8)
```
GET    /ai                            # AI console
GET    /ai/sessions                   # Agent sessions
GET    /ai/session/{id}               # Session detail
GET    /ai/prompts                    # Prompt history
GET    /ai/tools                      # Tool calls
GET    /ai/costs                      # Cost tracking
GET    /ai/latency                    # Latency dashboard
GET    /ai/failures                   # Error dashboard
```

## Regulations (10)
```
GET    /regulations                   # Regulatory center
GET    /regulations/sources           # Source list
GET    /regulations/source/{id}       # Source detail
GET    /regulations/list              # Regulation list
GET    /regulation/{id}               # Regulation detail
GET    /regulation/{id}/versions      # Version history
GET    /regulation/{id}/changes       # Change events
GET    /regulations/impact            # Impact analysis
GET    /regulations/affected-deals   # Affected deals
GET    /regulations/sync-history      # Sync log
```

# Executive Subdomain (`executive.spcnn.ru`)

## Executive Dashboard (10)
```
GET    /                             # Executive dashboard
GET    /kpi                          # KPI overview
GET    /risks                        # Risk overview
GET    /risk/{id}                    # Risk detail
GET    /compliance                   # Executive compliance
GET    /operations                   # Executive operations
GET    /warrooms                     # War room list
GET    /warroom/{id}                 # War room detail
GET    /recommendations              # Recommendations
GET    /reports                      # Executive reports
```

# Analytics Subdomain (`analytics.spcnn.ru`)

## Analytics (12)
```
GET    /                             # Analytics dashboard
GET    /business                     # Business dashboard
GET    /funnel                       # Funnel analysis
GET    /funnel/conversion            # Conversion metrics
GET    /funnel/duration              # Stage duration
GET    /portfolio                    # Portfolio analytics
GET    /team                         # Team performance
GET    /team/{id}                    # User performance detail
GET    /predictions                  # Prediction results
GET    /prediction/{id}              # Prediction detail
GET    /alerts                       # Alert list
GET    /alert/{id}                   # Alert detail
```

# Admin Subdomain (`admin.spcnn.ru`)

## Administration (20)
```
GET    /                             # Admin portal
GET    /admin/domains                # Domain settings
PUT    /admin/domains                # Update domains
GET    /admin/ai                     # AI provider settings
PUT    /admin/ai                     # Update AI settings
GET    /admin/mcp                    # MCP server list
GET    /admin/mcp/server/{id}        # MCP server detail
PUT    /admin/mcp/server/{id}        # Update MCP server
GET    /admin/telegram               # Telegram settings
PUT    /admin/telegram               # Update Telegram
GET    /admin/retention              # Retention settings
PUT    /admin/retention              # Update retention
GET    /admin/security               # Security settings
PUT    /admin/security               # Update security
GET    /admin/users                  # User management
GET    /admin/user/{id}              # User detail
PUT    /admin/user/{id}              # Update user
GET    /admin/roles                  # Role management
PUT    /admin/roles                  # Update roles
GET    /admin/audit-log              # Audit log
GET    /admin/settings               # All settings
```

## System Monitoring (12)
```
GET    /admin/system                 # System dashboard
GET    /admin/system/database        # Database status
GET    /admin/system/ai-providers    # AI provider status
GET    /admin/system/partitions      # Partition status
GET    /admin/system/storage         # Storage usage
GET    /admin/system/events          # Event bus status
GET    /admin/system/queues          # Queue status
GET    /admin/system/regulations     # Regulation sync
GET    /admin/system/migrations      # Migration status
GET    /admin/system/health          # Health check
GET    /admin/system/logs            # System logs
GET    /admin/system/metrics         # Prometheus metrics
```

# API Routes (administered from `api.spcnn.ru`)

Existing Sprint 1-8 APIs plus new:

## Platform Settings (5)
```
GET    /api/v1/platform/settings     # Get all settings
PUT    /api/v1/platform/settings     # Update settings
GET    /api/v1/platform/domains      # Get domain config
GET    /api/v1/platform/health       # Health check
GET    /api/v1/platform/version      # Version info
```

## User Management (4)
```
GET    /api/v1/users                 # List users
GET    /api/v1/users/{id}            # User detail
PUT    /api/v1/users/{id}            # Update user
DELETE /api/v1/users/{id}            # Delete user
```

## Session Management (3)
```
POST   /api/v1/auth/login            # Login
POST   /api/v1/auth/logout           # Logout
GET    /api/v1/auth/session          # Current session
```

**Total: 180 routes** (CRM: 96, Executive: 10, Analytics: 12, Admin: 32, API: 30)
