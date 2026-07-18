#!/usr/bin/env python3
import os

def write_file(p, content):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w') as f:
        f.write(content.strip() + "\n")
    print(f"Wrote {p} ({len(content)} bytes)")

adr = r"""|# ADR-0014 — Telegram Staff Assistant V1

**Date:** 2026-06-07
**Status:** Proposed
**Sprint:** 3
**Editor:** Principal Architect
**Previous:** ADR-0013 Lead Management (Accepted)
**Related:** ADR-0010 Soft Delete & Audit, ADR-0012 Architecture Freeze

## Context

Real Estate OS has completed:

- Sprint 1: Infrastructure Foundation (T1 Config, T2 Database, models, migrations)
- Sprint 1B: Runtime Foundation (exceptions, structlog, middleware, error handlers, health checks)
- Sprint 2: CRM Service Layer (7 repositories, 6 services, conversion engine, schemas, API)

The system now has full backend capabilities but zero user-facing UI.

Employees currently cannot:
- View or manage leads without SQL access
- Track client assignments
- Receive notifications about new leads or task assignments
- Perform CRM operations from mobile devices

A Telegram-based staff assistant solves this by providing a mobile-first interface built on top of the existing CRM API.

## Decision

Implement a Telegram bot using aiogram 3.x as the exclusive staff interface for CRM operations.

### Key Architectural Rules

1. Bot never accesses PostgreSQL directly. All data flows through the CRM API layer.
2. Bot contains NO business logic. Business rules live in CRM Services.
3. Bot operates under strict role-based access control. Only authenticated employees with valid roles.
4. Every bot action generates an audit event with source_component=telegram_bot.
5. Bot captures observability metrics for monitoring and debugging.

### Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Framework | aiogram 3.x | FSM, middleware, DI, router architecture, async |
| API Client | httpx | Async, connection pooling, timeout support |
| Auth | Telegram ID + roles table | No external auth, uses existing users.telegram_id |
| Notifications | aiogram Bot.send_message | Direct push, no polling |
| Metrics | Prometheus metrics | T4.5 compatible |

## Consequences

### Positive
- Mobile-first CRM access for all employees
- Reuses existing CRM API — no dual-implementation risk
- FSM enables multi-step workflows
- Middleware architecture enables auth, audit, metrics without handler code
- Separation of concerns: bot is thin client, backend is source of truth
- Future Knowledge Agent and client bot can share the same API layer

### Negative
- Requires stable API connectivity (bot dead if API is down)
- Additional deployment: manage aiogram polling/webhook process
- Telegram callback_data limited to 64 bytes — compact encoding required
- No offline capability

### Architecture Constraints
1. All CRM mutations through service layer (no direct SQL)
2. All read queries through repository layer
3. Soft delete enforced at API level
4. Audit events mandatory for: create, update, delete, restore, status_change, assign
5. source_component=telegram_bot for all audit events
"""

write_file("/home/xiag/real-estate-os/docs/adr/0014-telegram-staff-assistant-v1.md", adr)
print("ADR-0014 DONE")
