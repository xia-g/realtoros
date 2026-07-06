# Project Vision — Real Estate OS

## Mission

Создать AI-native операционную систему для агентств недвижимости, 
которая автоматизирует полный цикл сделки: от лида до регистрации права собственности.

## Core Principles

1. **AI-first** — каждый аспект работы усилен AI: compliance, анализ рисков, генерация документов, прогнозирование
2. **Knowledge-driven** — все решения обоснованы knowledge graph с explainability
3. **Compliance-by-design** — сделки не могут быть завершены без прохождения compliance gates
4. **Multi-tenant** — архитектура поддерживает любое количество агентств на одном инстансе
5. **Domain-driven** — модели предметной области в центре, а не таблицы БД

## Stack

- **Backend:** Python 3.13, FastAPI, SQLAlchemy 2, PostgreSQL 17
- **Frontend:** Next.js 15, TypeScript Strict, Tailwind v4, TanStack Query, Zustand
- **AI:** DeepSeek, OpenAI, Knowledge Graph, Agent Runtime
- **Ports:** API :8090, Frontend :3000
- **Database:** `realtoros` @ 127.0.0.1:5432 (user: realtoros)

## Status: Production Ready ✅ (Sprint 8.8 completed)
## Sprint UI-1 ✅ (5 subdomains, 180 routes)
## Sprint UI-2 ✅ (CRM, Deal Workspace, Copilot, Admin frontend)
