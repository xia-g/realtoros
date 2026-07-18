# RealtorOS Architecture Freeze v2

**Date:** July 2026
**Status:** FROZEN — no architectural changes without new ADR
**Architectural Epoch:** Knowledge Access Platform

## Architecture in Three Lines

1. **v1.x** — Document Processing Platform: OCR → Semantic → Accounting (implemented)
2. **v2.0** — Knowledge Platform: Facts → Identity → Agreements → Graph → Revisions (implemented, 297 tests)
3. **v2.1** — Knowledge Access Platform: Query → Engine → Projections → Infrastructure (architecture frozen)

## What Made the Freeze

- 16 Architecture Decision Records (ADR-001 through ADR-016)
- 35 domain invariants across all layers
- 10 architectural principles
- Layer contracts with strict dependency rules
- Complete domain terminology (120+ terms)
- 297 unit tests passing in the domain layer

## Current State

| Layer | Module | Status | Tests |
|-------|--------|--------|-------|
| v1.x | OCR / Semantic / Accounting | ✅ Implemented | — |
| v2.0.1a | Neutral Facts | ✅ Implemented | 17 |
| v2.0.2 | Agreement Resolution | ✅ Implemented | 17 |
| v2.0.3 | Canonical Identity | ✅ Implemented | 22 |
| v2.0.4 | Knowledge Evolution | ✅ Implemented | 38 |
| v2.0.5 | Knowledge Graph | ✅ Implemented | 49 |
| v2.0.6 | Knowledge State | ✅ Implemented | 24 |
| v2.1.1 | Projection Layer | 🔒 Frozen | — |
| v2.1.2 | Knowledge Query | 🔒 Frozen | — |
| v2.1.3 | Query Engine | 🔒 Frozen | — |
| v2.1.4 | Infrastructure | 🚧 Future | — |
| v3.x | Enterprise OS | 🚧 Future | — |

## Architectural Principles

| # | Principle | Applies to |
|---|-----------|-----------|
| 1 | Domain owns knowledge | All layers |
| 2 | Projection owns read performance | v2.1.1 |
| 3 | Plan describes WHAT | v2.1.1 |
| 4 | Executor decides HOW | v2.1.1 |
| 5 | Store decides WHERE | v2.1.1 |
| 6 | Query decides HOW TO READ | v2.1.2 |
| 7 | Domain never imports outer layers | All layers |
| 8 | Facts are immutable | v2.0 |
| 9 | Revisions are append-only | v2.0.6 |
| 10 | Graph is pure domain abstraction | v2.0.5 |

## Key Documents

- `dependency_rules.md` — who imports whom
- `layer_contracts.md` — input/output per layer
- `terminology.md` — complete glossary
- `invariants.md` — all 35 invariants
- `ADR-001` through `ADR-016` — all architecture decisions
