# Epic 3 — Remediation Plan

## Timing Issue — document.ready vs promote-to-deal

### Current (Temporary) Solution
- `document.ready` эмитится до promote-to-deal
- promote-to-deal переэмитирует `document.ready` после установки promoted_deal_id
- DCR consumer обрабатывает переэмитированный event

### Long-term Architecture Decision Needed

**Вопрос:** Какой event должен триггерить DCR?

**Варианты:**
1. **deal.document_attached** — новый event после promote-to-deal
2. **deferred DCR** — DCR сохраняет event пока deal не найден, обрабатывает позже
3. **delayed document.ready** — document.ready эмитится только после promote-to-deal
4. **DCR subscribes to deal lifecycle** — DCR подписан на события сделок

### Acceptance Criteria for Long-term Fix
- [ ] Нет переэмитирования document.ready
- [ ] DCR может найти сделку по canonical mapping
- [ ] Нет race conditions между document.ready и promote-to-deal
- [ ] Architecture Freeze Record обновлён
