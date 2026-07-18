# Project Status

## Active
- Backend API running on :8090
- Frontend (Next.js) running on :3000
- Database realtoros populated: 100 clients, 50 properties, 30 deals, 212 documents
- 4 regulations loaded (218-ФЗ, 102-ФЗ, 214-ФЗ, 115-ФЗ)
- 25 migrations applied
- 72 partitions created (3 tables × 12 months)
- MCP server at mcp/server/ (FastMCP)

## Pending
- Production deployment with NGINX reverse proxy
- DNS setup for 5 subdomains
- SSL certificates (Let's Encrypt)

## Infrastructure → Completed
- Database: realtoros @ 127.0.0.1:5432 (user: realtoros)
- Backend port changed from 8000 to 8090
- Frontend port: 3000
- PostgreSQL trust auth → realtoros user with password

## Frontend → Completed
- next build succeeds (0 type errors)
- Layout: sidebar + content + copilot drawer
- Pages: Dashboard, Login, Deals list, Deal Workspace ([id]), Clients, Documents, Operations, Admin
- Admin page: domains, settings, health widgets

## Backend Fixes → Completed
- Fixed structlog logging config (ProcessorFormatter compatibility)
- Fixed corrupted api/router.py
- Fixed missing dependencies (apscheduler, tiktoken, langchain-core)
