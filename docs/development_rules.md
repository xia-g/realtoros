# Development Rules

## Architecture

- **AP-1 Zero Hardcode:** All domains via config, never in code
- **AP-2 Domain Registry:** platform_settings table
- **AP-3 Multi-Tenant Ready:** No spcnn.ru binding
- **AP-4 Backend First:** UI uses only public APIs, no direct DB access, no duplicated business logic

## Code Style

- Python 3.13, PEP 8, 4-space indent, type hints on all new functions
- SQLAlchemy 2 ORM with async sessions
- Pydantic v2 for all API schemas
- snake_case for functions/vars, UPPER_SNAKE for config

## git Workflow

- Conventional commits (feat:, fix:, docs:, refactor:, chore:)
- Feature branches → PR → squash merge
- No secrets in commits (use .env)

## MCP Access

- MCP server at `mcp/server/main.py` (FastMCP)
- Documentation in `docs/` — tools read from `docs/vision/`, `docs/architecture/`, `docs/domain/`, `docs/roadmap/`
- Backlog in `docs/backlog.json`
- Status in `docs/project_status.md`

## Frontend

- Next.js 15 App Router, TypeScript strict
- Tailwind v4, shadcn/ui patterns
- TanStack Query for server state, Zustand for client state
- All API calls through typed client in `frontend/lib/api-client.ts`
