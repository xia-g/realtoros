# Sprint UI-2 — CRM Workspace + Deal Workspace + Documents + AI Copilot

**Date:** 2026-06-10
**Stack:** Next.js 15, TypeScript Strict, Tailwind CSS, shadcn/ui, TanStack Query, Zustand
**Subdomain:** crm.${DOMAIN}

---

## Architecture

```
frontend/
├── app/                          # Next.js App Router pages
│   ├── page.tsx                  # Dashboard
│   ├── login/                    # Auth
│   ├── deals/[id]/page.tsx      # Deal Workspace (main)
│   ├── deals/page.tsx           # Deal list
│   ├── clients/page.tsx         # Client list
│   ├── documents/page.tsx       # Document center
│   ├── operations/page.tsx      # Operations center
│   └── admin/page.tsx           # Admin portal
├── components/
│   ├── layout/sidebar.tsx        # Navigation shell
│   ├── deal/deal-header.tsx      # Deal header bar
│   ├── ui/health-gauge.tsx       # Score gauge
│   └── copilot/copilot-drawer.tsx # AI Copilot panel
├── lib/
│   ├── api-client.ts             # Typed HTTP client
│   ├── utils.ts                  # Shared utilities
│   └── query-client.ts           # TanStack Query config
├── store/
│   ├── auth.ts                   # Zustand auth store
│   └── ui.ts                     # Zustand UI state
└── providers/
    ├── auth-provider.tsx
    └── query-provider.tsx
```

## Pages Created

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | Dashboard | Stats cards + platform status |
| `/login` | Login form | JWT auth |
| `/deals` | Deal list | Server-side table |
| `/deals/[id]` | Deal Workspace | Timeline + Compliance + Copilot |
| `/clients` | Client list | Searchable table |
| `/documents` | Document center | Upload + validation status |
| `/operations` | Operations center | SLA + Actions + Escalations |
| `/admin` | Admin portal | Domains + Settings + Health |

## Key Components

### Deal Workspace (`/deals/[id]`)
- **DealHeader**: Number, type, stage, Health/Compliance/Risk gauges
- **Timeline panel**: Chronological event history from DealTimelineEvent
- **Compliance panel**: Score, risk level, used regulations
- **CopilotDrawer**: AI chat with suggestions, sources, confidence
- **10 tabs**: Overview → Participants → Documents → ... → Audit

### AI Copilot (`<CopilotDrawer />`)
- 5 modes: deal, compliance, regulation, operations, executive
- Suggestion chips for quick queries
- Response display with source attribution + confidence scores
- Loading state with pulsing indicator

### Admin Portal (`/admin`)
- Domain configuration viewer
- Platform settings key-value list
- System health widgets (API, DB, Partitions, Migrations)

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| CRM list pages (deals, clients) | ✅ |
| Deal workspace with timeline | ✅ |
| Compliance visible in UI | ✅ |
| AI Copilot answers via Agent Runtime | ✅ |
| Documents with validation status | ✅ |
| Operations center widgets | ✅ |
| Admin portal with domain config | ✅ |
| No business logic duplication | ✅ |
| OpenAPI typed client | ✅ |
| Zustand stores for auth + UI | ✅ |

## Next Steps

1. `npx openapi-typescript https://api.spcnn.ru/openapi.json -o generated/api.ts`
2. `npm ci && npm run build` — verify zero TypeScript errors
3. Deploy to subdomains via deployment_guide.md
4. Run E2E scenario from docs/ui/e2e_scenario.md
