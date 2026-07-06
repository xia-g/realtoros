# Sprint UI-1 — UI Architecture

## Stack

- **Framework:** Next.js 14+ (App Router)
- **Language:** TypeScript 5+
- **Styling:** Tailwind CSS 3
- **State:** Zustand (client) + TanStack Query (server)
- **API:** fetch() via generated API client
- **Auth:** JWT in httpOnly cookies

## Subdomain Architecture

```
crm.spcnn.ru/       → Next.js app (CRM + Deals + Docs + Ops)
executive.spcnn.ru/ → Next.js app (Executive Dashboard)
analytics.spcnn.ru/ → Next.js app (Analytics)
admin.spcnn.ru/     → Next.js app (Admin + Monitoring)
api.spcnn.ru/       → FastAPI (existing)
```

Each frontend is a standalone Next.js app sharing:
- `@realtor/ui` — component library (Tailwind)
- `@realtor/api-client` — generated API client (openapi-typescript)
- `@realtor/auth` — JWT auth helpers

## Component Hierarchy

```
AppShell
├── Sidebar (context-aware per subdomain)
│   ├── NavSection (grouped links)
│   └── UserMenu (profile, logout)
├── Header
│   ├── Breadcrumbs
│   ├── GlobalSearch
│   └── Notifications
└── MainContent
    ├── DataTable (reusable: TanStack Table)
    ├── DetailPanel
    │   ├── Tabs (context-aware)
    │   └── Sections
    ├── FormBuilder (auto-generated from OpenAPI schemas)
    ├── StatusBadge
    ├── HealthGauge (0-100 score display)
    ├── Timeline (event chain display)
    ├── DiagramFlow (knowledge graph, workflow)
    └── AIChat (agent interaction panel)
```

## Data Flow

```
User Action
  → React Component
    → TanStack Query mutation
      → API Client (generated)
        → HTTP fetch to api.spcnn.ru
          → FastAPI endpoint
            → Service Layer
              → Repository
                → PostgreSQL
  ← Response cached in Zustand
  ← UI updated reactively
```

## Key Components

### DataTable
- Server-side pagination, sorting, filtering
- Column visibility toggle
- Export to CSV
- Row actions menu

### DetailPanel / Tabs
- Dynamic tabs based on entity type
- Lazy-loaded tab content
- Breadcrumb trail

### HealthGauge
- Circular gauge 0-100
- Color: green(>85) → yellow(>70) → orange(>50) → red
- Component breakdown bars

### Timeline
- Vertical event list
- Color-coded by event type
- Expandable detail per event
- Paginated with infinite scroll

### AIChat
- Chat bubble interface
- Source references panel (expandable)
- Tool call visualization
- Token/cost display
- Confidence score per source

## State Management

```typescript
// Zustand stores
interface AuthStore {
  user: User | null;
  token: string | null;
  login: (credentials) => void;
  logout: () => void;
}

interface UIStore {
  sidebar: 'expanded' | 'collapsed';
  theme: 'light' | 'dark';
  currentDeal: UUID | null;
}

// TanStack Query for server state
// Each API endpoint has a dedicated query hook
```

## API Client Generation

```bash
npx openapi-typescript https://api.spcnn.ru/openapi.json -o types/api.ts
```

This generates TypeScript types for all 180+ endpoints.
