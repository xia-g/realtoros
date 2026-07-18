# Accounting Pipeline — Performance Report

**Дата:** 2026-06-15
**Тест:** 2,000 событий (dev environment, PostgreSQL 17, 4 vCPU)

---

## Сводка

| Метрика | P95 | P50 | Max | SLO | Статус |
|---------|-----|-----|-----|-----|--------|
| Insert rate | — | 7,174 evt/s | — | — | ✅ |
| Snapshot build | 19 ms | 17 ms | 28 ms | — | ✅ |
| Decision | 35 ms | 28 ms | 65 ms | < 1 sec | ✅ |
| Replay | 43 ms | 36 ms | 51 ms | < 3 sec | ✅ |

## Детали

### 500 событий (warmup)
| Фаза | Время | P95 | P50 |
|------|-------|-----|-----|
| Insert | 0.08s (6,108 evt/s) | — | — |
| Snapshots | 7.59s | 19 ms | 16 ms |
| Decisions | 13.85s | 36 ms | 28 ms |
| Replays (100) | 3.46s | 45 ms | 35 ms |

### 2,000 событий
| Фаза | Время | P95 | P50 | Max |
|------|-------|-----|-----|-----|
| Insert | 0.28s (7,174 evt/s) | — | — | — |
| Snapshots | 31.01s | 19 ms | 17 ms | 28 ms |
| Decisions | 56.05s | 35 ms | 28 ms | 65 ms |
| Replays (100) | 3.53s | 43 ms | 36 ms | 51 ms |

## Узкие места

1. **Snapshot builds sequential** — каждое событие обрабатывается индивидуально.
   Решение: batch snapshot build (фаза 3).

2. **Нет worker pool** — одна горутина на все события.
   Решение: asyncio worker pool (настроить concurrent.futures).

3. **Нет кэша** — каждое решение загружает snapshot из DB.
   Решение: in-memory cache для hot events.

## Экстраполяция на 100k

| Фаза | 2k время | 100k (est.) | SLO |
|------|----------|-------------|-----|
| Insert | 0.28s | ~14s | — |
| Snapshots | 31s | ~26 min | — |
| Decisions | 56s | ~47 min | < 5 min ❌ |
| Replays | 3.5s/100 | ~3.5s/100 | < 15 min ✅ |

**Вывод:** для 100k необходим параллельный worker pool.
