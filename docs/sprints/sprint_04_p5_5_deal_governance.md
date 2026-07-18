# Sprint 4 — Phase P5.5: Deal Governance Foundation

**Date:** 2026-06-09
**Status:** Completed
**Pre-requisite for:** P6 Agent Runtime (check_deal_completeness tool)
**Depends on:** Existing Deal model, DealCheckpoint, DocumentRequirement, Regulation

---

## Purpose

Перед P6 Agent Runtime добавить слой governance для сделок.

Агент должен уметь:
- проверить, готова ли сделка к следующему этапу
- определить, какие документы отсутствуют
- сослаться на нормативный акт при ответе

---

## Architecture

```
Deal
  ├─ DealCheckpoint[] — обязательные этапы (client_verified, contract_signed, ...)
  ├─ DocumentRequirement[] — требования к документам по типу сделки
  └─ Regulation[] — нормативные акты (Минфин, ФНС, Росреестр, ЦБ, Госуслуги)
        └─ trust_level: OFFICIAL | VERIFIED | COMMUNITY | LLM_GENERATED

ComplianceService.evaluate_deal()
  ├─ 1. Проверить чекпоинты по этапам
  ├─ 2. Проверить документы по типу сделки
  ├─ 3. Вычислить compliance_score
  └─ 4. Вернуть список недостающих элементов

MCP Tools:
  ├─ check_deal_completeness(deal_id, deal_type) → score + missing items
  ├─ validate_document_package(deal_type, uploaded_docs) → completeness %
  └─ get_regulation(query, min_trust) → matching regulations
```

## Files Created (8)

| File | Purpose |
|------|---------|
| `backend/models/deal_checkpoint.py` | DealCheckpoint model (stage, checkpoint_key, is_completed) |
| `backend/models/document_requirement.py` | DocumentRequirement (deal_type, document_type, is_required) |
| `backend/models/regulation.py` | Regulation (title, source, trust_level, version, content, hash) |
| `backend/repositories/deal_checkpoint_repository.py` | CRUD + completion stats + by deal/stage |
| `backend/repositories/document_requirement_repository.py` | CRUD + by deal type + required only |
| `backend/repositories/regulation_repository.py` | Search + by source + by category |
| `backend/services/compliance_service.py` | ComplianceEngine: evaluate_deal(), check_deal_completeness(), validate_document_package() |
| `backend/services/regulation_service.py` | RegulationService: search_regulations(), get_regulation() |

## Files Modified (4)

| File | Change |
|------|--------|
| `backend/models/__init__.py` | Added DealCheckpoint, DocumentRequirement, Regulation |
| `backend/models/deal.py` | Added checkpoints relationship |
| `mcp/server/main.py` | Added 3 deal governance MCP tools |
| `mcp/server/tools/deal_tools.py` | Created (MCP-facing wrappers) |

## Migrations (2)

| Migration | Tables |
|-----------|--------|
| `009_add_deal_checkpoints_and_doc_reqs.py` | deal_checkpoints, document_requirements |
| `010_add_regulations.py` | regulations |

## Trust Levels

```
OFFICIAL         — официальные тексты (Минфин, ФНС, Росреестр, ЦБ)
VERIFIED         — проверенные источники (Госуслуги)
COMMUNITY        — сообщество (риелторские ассоциации)
LLM_GENERATED    — сгенерировано AI (требует проверки)
```

## Deal Type Checklists

| Type | Stages | Checkpoints |
|------|--------|-------------|
| SALE_APARTMENT | 4 (NEW, PREPARATION, SIGNING, REGISTRATION) | 10 checkpoints |
| MORTGAGE | 4 (NEW, PREPARATION, SIGNING, REGISTRATION) | 11 checkpoints |
| RENT | 3 (NEW, PREPARATION, SIGNING) | 7 checkpoints |

## Compliance Score Formula

```
score = completed_items / total_items * 100

total_items = checkpoints + required_documents
completed_items = completed_checkpoints + uploaded_documents

status:
  100%      → compliant
  50-99%    → partial (with missing items list)
  <50%      → non_compliant
```

## MCP Tools

| Tool | Parameters | Returns |
|------|-----------|---------|
| `check_deal_completeness` | deal_id, deal_type, completed_checkpoints, uploaded_documents | score, missing_items, stage_summary |
| `validate_document_package` | deal_type, uploaded_documents | completeness %, missing_required, missing_recommended |
| `get_regulation` | query, min_trust, limit | title, source, trust_level, version, effective_from |

## Integration

- **P3 Context Builder** может использовать `get_regulation()` для поиска нормативных актов
- **P6 Agent Runtime** использует `check_deal_completeness()` как Tool
- **SystemJobs** (для regulation_sync_daily) — задел
- **UI** — compliance dashboard может читать результаты evaluate_deal()

## Next: P6 Agent Runtime

P5.5 даёт Agent Runtime 3 готовых инструмента для работы со сделками.
