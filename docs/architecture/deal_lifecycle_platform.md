# Deal Lifecycle & Compliance Platform — Architecture

**Sprint 5 — June 2026**
**Production Readiness Target: 95/100**

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Deal Copilot (MCP)                    │
│  check_deal_status | check_deal_risks | get_next_actions│
│  get_regulation_updates | check_deal_completeness        │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│                 Agent Runtime (P6)                       │
│         Intent → Plan → Tools → Context → LLM           │
└───────┬────────────┬─────────────┬──────────────────────┘
        │            │             │
┌───────▼────┐ ┌────▼────┐ ┌──────▼────────────────┐
│  Workflow  │ │Compliance│ │   Risk Assessment     │
│   Engine   │ │  Engine  │ │      Engine           │
├────────────┤ ├─────────┤ ├────────────────────────┤
│ 10 stages  │ │ Score    │ │ 8 risk factors        │
│ transitions│ │ 0-100%   │ │ LOW to CRITICAL       │
│ checkpoints│ │ blocking │ │ recommendations       │
└───────┬────┘ └──┬───┬───┘ └────────────────────────┘
        │         │   │
┌───────▼─────────▼───▼─────────────────────────────────┐
│             Document Package Manager                   │
│  Required | Optional | Conditional → completeness %    │
└─────────────────────┬─────────────────────────────────┘
                      │
┌─────────────────────▼─────────────────────────────────┐
│             Regulation Intelligence                    │
│  Sources: Росреестр | ФНС | Минфин | ЦБ | Госдума    │
│  ┌─────────┐  ┌───────────┐  ┌──────────────┐        │
│  │Versioning│  │Sync Jobs  │  │Impact Analysis│       │
│  └─────────┘  └───────────┘  └──────────────┘        │
└─────────────────────────────────────────────────────────┘
```

## Domain Model

```
DealWorkflow (1) ──── (N) DealStageTransition
       │
Deal (1) ──── (N) DealDocumentPackage
       │
       └─── (N) DealRiskAssessment

Regulation (1) ──── (N) RegulationVersion (1) ── (1) RegulationImpact
RegulationSyncJob (standalone)

DealCheckpoint (1) ──── Deal (N)   [P5.5]
DocumentRequirement (1) ──── Deal (N)  [P5.5]
```

## Stage Lifecycle

```
LEAD → PROPERTY_SELECTION → NEGOTIATION → ADVANCE_PAYMENT →
DOCUMENT_COLLECTION → BANK_APPROVAL → SIGNING →
REGISTRATION → TRANSFER → CLOSED
```

Each stage has required checkpoints. Transitions validate conditions.

## Compliance Score

```
score = (completed_checkpoints + uploaded_documents) / total_items * 100

status:
  100%      → compliant
  50-99%    → partial
  <50%      → non_compliant

check_registration_readiness:
  contract_signed ✓ + passports ✓ + EGRN extract → ready
```

## Risk Factors (8)

| Factor | Weight | Description |
|--------|--------|-------------|
| ownership_period < 1yr | 15 | Short ownership → higher risk |
| minor_owners | 25 | Requires опека разрешение |
| power_of_attorney | 20 | Check validity and scope |
| mortgage | 15 | Bank consent required |
| inheritance | 20 | Timing check needed |
| court_restrictions | 30 | Must be resolved before sale |
| arrests | 35 | Must be lifted |
| missing_documents | 10 each | Document gaps |
| regulatory_conflicts | 25 each | Legal conflicts |

## MCP Tools (9 total)

### Governance (P5.5)
- check_deal_completeness
- validate_document_package
- get_regulation

### Deal Copilot (Sprint 5)
- check_deal_status — overall status (compliance + risk)
- check_deal_risks — risk factors assessment
- get_regulation_updates — recent changes from official sources
- get_next_actions — recommended next steps
