# E2E Scenario — Real Deal from Lead to Registration

**Purpose:** Verify all 12 sprints on live data through the UI.
**Roles:** Realtor (creates lead), Compliance (checks), Lawyer (documents), Executive (approves)

---

## Step 1: Lead Creation (Sprint 1-2)

1. **Realtor** opens `crm.spcnn.ru/leads/new`
2. Fills: source="телефонный звонок", full_name="Иван Петров", phone="+79001234567", interest_type="buy", budget_max=15000000
3. Clicks "Создать лид"
4. **Expected:** Lead created with status="new". Created in DB via `LeadService.create_lead()`. Event `lead.created` emitted (Sprint 8.6).

## Step 2: Lead Qualification (Sprint 2, ADR-0013)

1. **Realtor** opens `crm.spcnn.ru/lead/{id}`
2. Changes status to "qualifying", adds note
3. Changes status to "qualified", sets priority="hot"
4. **Expected:** Status machine validates via ADR-0013. LeadEvent recorded.

## Step 3: Lead → Client Conversion (Sprint 2)

1. **Realtor** clicks "Конвертировать в клиента"
2. System creates Client + optionally creates Deal
3. **Expected:** `LeadService.convert_lead()` called. Client created. Lead status = "converted". Event `lead.converted` emitted (Sprint 8.6).

## Step 4: Deal Creation (Sprint 5)

1. **Realtor** opens `crm.spcnn.ru/deals/new`
2. Selects client, property, deal_type="mortgage"
3. **Expected:** Deal created. Playbook "mortgage" attached automatically (Sprint 6B). SLA generated. Timeline event created.

## Step 5: Document Upload (Sprint 5)

1. Opens `crm.spcnn.ru/deal/{id}/documents`
2. Uploads: passport, EGRN extract, purchase agreement
3. **Expected:** Documents stored. `DocumentPackageService.attach_document()` called. Event `document.created` emitted (Sprint 8.6).

## Step 6: Document Validation (Sprint 6B P5)

1. Opens `crm.spcnn.ru/document/{id}/validate`
2. **Expected:** `DocumentValidationService.validate_document()` runs. Returns score + issues + warnings.

## Step 7: Compliance Check (Sprint 5)

1. **Compliance officer** opens `crm.spcnn.ru/compliance`
2. Clicks "Проверить сделку" for deal
3. **Expected:** `ComplianceService.evaluate()` runs. Score calculated. ComplianceAudit entry created (Sprint 5.2). Events flow via DomainEventBus.

## Step 8: Regulatory Check (Sprint 6A)

1. Opens `crm.spcnn.ru/regulations/impact`
2. Checks which regulations apply to deal
3. **Expected:** `RegulationImpactServiceV2` returns affected regulations. 218-ФЗ, 102-ФЗ detected for mortgage.

## Step 9: Risk Assessment (Sprint 5)

1. Opens `crm.spcnn.ru/deal/{id}/risks`
2. **Expected:** RiskEngine generates risks. Scores displayed. Timeline events created.

## Step 10: Deal Health (Sprint 6B P6)

1. Opens `crm.spcnn.ru/deal/{id}/operations`
2. **Expected:** Health score calculated (compliance 30% + risk 20% + SLA 20% + docs 15% + activity 15%). Each component visible.

## Step 11: AI Copilot (Sprint 4, 8)

1. Opens `crm.spcnn.ru/deal/{id}/ai`
2. Asks: "Какие документы отсутствуют?"
3. **Expected:** Agent Runtime responds with sources, confidence, tool calls. `agent_tool_calls` logged. `ai_call_log` recorded.

## Step 12: Analytics (Sprint 7A)

1. **Executive** opens `analytics.spcnn.ru/funnel`
2. **Expected:** Deal visible in funnel. Stage duration calculated. Conversion metrics updated.

## Step 13: Executive Dashboard (Sprint 7B)

1. **Executive** opens `executive.spcnn.ru`
2. **Expected:** Dashboard shows deal status. Health score. Critical alerts. War rooms.

## Step 14: Autonomous Operations (Sprint 8)

1. Inject a missing document scenario
2. **Expected:** Task generated. Assigned. Escalation if not completed. Approval required.

## Step 15: Deal Closure

1. Move deal through stages: verification → mortgage → registration → closing
2. **Expected:** Each transition fires event. Timeline populated. Final ComplianceAudit created.

## Verification Points

| # | Check | Sprint | Expected |
|---|-------|--------|----------|
| V1 | Lead in DB | 1-2 | `leads` table |
| V2 | Client linked to lead | 2 | `clients` + `leads.client_id` |
| V3 | Deal with playbook | 5, 6B | `deals` + `deal_playbooks` |
| V4 | Documents uploaded | 5 | `documents` + `deal_document_packages` |
| V5 | Compliance audit | 5, 5.2 | `compliance_audits` |
| V6 | Regulations affecting deal | 6A | `regulation_impacts` |
| V7 | Deal health score | 6B | `deal_health_snapshots` |
| V8 | Agent answered | 4, 8 | `agent_tool_calls` + `ai_call_log` |
| V9 | Funnel shows deal | 7A | Analytics query |
| V10 | Executive dashboard | 7B | Dashboard endpoint |
| V11 | Autonomous tasks | 8 | GeneratedTask table |

## Pass Criteria

All 11 verification points must pass.
