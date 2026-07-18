# RBAC Matrix — Sprint UI-1

**Roles:** Executive, Admin, Broker, Realtor, Lawyer, Compliance, Accountant, Viewer

---

| Page / Section | Executive | Admin | Broker | Realtor | Lawyer | Compliance | Accountant | Viewer |
|---------------|-----------|-------|--------|---------|--------|------------|------------|--------|
| **Dashboard** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **CRM / Clients** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | read |
| **CRM / Properties** | ✅ | ✅ | ✅ | ✅ | read | read | read | read |
| **CRM / Leads** | ✅ | ✅ | ✅ | ✅ | read | ✅ | read | read |
| **Deal Workspace** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | read |
| /deal/{id}/overview | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | read |
| /deal/{id}/participants | ✅ | ✅ | ✅ | ✅ | ✅ | read | ✅ | read |
| /deal/{id}/documents | ✅ | ✅ | ✅ | ✅ | ✅ | read | ✅ | read |
| /deal/{id}/workflow | ✅ | ✅ | ✅ | ✅ | read | ✅ | read | read |
| /deal/{id}/compliance | ✅ | ✅ | read | read | ✅ | ✅ | read | read |
| /deal/{id}/risks | ✅ | ✅ | read | read | ✅ | ✅ | read | read |
| /deal/{id}/timeline | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | read |
| /deal/{id}/operations | ✅ | ✅ | ✅ | ✅ | read | read | read | ❌ |
| /deal/{id}/ai | ✅ | ✅ | ✅ | ✅ | read | ✅ | read | ❌ |
| /deal/{id}/audit | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| **Documents** | ✅ | ✅ | ✅ | ✅ | ✅ | read | read | read |
| **Compliance** | ✅ | ✅ | read | read | ✅ | ✅ | read | read |
| **Operations** | ✅ | ✅ | ✅ | ✅ | read | read | read | ❌ |
| /operations/actions/approve | ✅ | ✅ | read | read | ❌ | read | ❌ | ❌ |
| /operations/escalations | ✅ | ✅ | read | read | ❌ | read | ❌ | ❌ |
| /operations/recovery | ✅ | ✅ | read | read | ❌ | read | ❌ | ❌ |
| **Knowledge** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **AI Console** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Regulations** | ✅ | ✅ | read | read | ✅ | ✅ | read | read |
| **Analytics** | ✅ | ✅ | ✅ | read | read | read | ✅ | read |
| /analytics/funnel | ✅ | ✅ | ✅ | read | ❌ | read | ❌ | read |
| /analytics/team | ✅ | ✅ | ✅ | read | ❌ | ❌ | ❌ | ❌ |
| /analytics/predictions | ✅ | ✅ | read | read | read | read | ❌ | ❌ |
| **Executive** | ✅ | read | read | ❌ | read | read | read | ❌ |
| /executive/warrooms | ✅ | read | ❌ | ❌ | read | ✅ | ❌ | ❌ |
| /executive/recommendations | ✅ | read | read | ❌ | read | ✅ | ❌ | ❌ |
| **Admin / Settings** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Admin / Domains** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Admin / AI** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Admin / MCP** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Admin / Telegram** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Admin / Retention** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Admin / Security** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Admin / Users** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Admin / Roles** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **System Monitoring** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Autonomous Ops** | ✅ | ✅ | read | read | ❌ | read | ❌ | ❌ |
| /autonomous/approvals | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
