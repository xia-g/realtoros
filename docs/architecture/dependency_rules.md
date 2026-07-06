# Dependency Rules

**Single page. Never violated.**

```
┌─ v1.x: Document Processing Platform ─────┐
│  OCR → Semantic → Accounting             │
│  MAY NOT import v2.0                     │
└──────────────────────────────────────────┘

┌─ v2.0: Domain (Knowledge Platform) ─────┐
│  Facts, Entities, Agreements, Graph     │
│  NEVER imports: anything                │
│  Imported by: everything                │
└──────────────────────────────────────────┘

┌─ v2.1.1: Projection Layer ──────────────┐
│  Builders, Plans, Store                 │
│  MAY import: Domain (v2.0)             │
│  NEVER imports: Query, Engine          │
│  Imported by: Engine, Infrastructure    │
└──────────────────────────────────────────┘

┌─ v2.1.2: Knowledge Query ──────────────┐
│  Intent Document, Predicates           │
│  MAY import: Domain (subject types)    │
│  NEVER imports: Engine, Projection     │
│  Imported by: Engine                   │
└──────────────────────────────────────────┘

┌─ v2.1.3: Query Engine ─────────────────┐
│  Planner, Optimizer, Resolver          │
│  MAY import: Domain, Projection, Query │
│  NEVER imports: Infrastructure         │
│  Imported by: Infrastructure           │
└──────────────────────────────────────────┘

┌─ v2.1.4: Infrastructure ──────────────┐
│  Adapters, Providers, API             │
│  MAY import: everything               │
│  NEVER imported by: Domain            │
└──────────────────────────────────────────┘
```

## In One Sentence

> Each layer imports only layers below it.
>
> Domain imports nothing.
>
> Infrastructure may import everything.
>
> No layer may import a layer above itself.

## Violation Detection

```python
# Runtime check (in tests)
def test_domain_does_not_import_projection():
    import domain
    assert "knowledge_projection" not in sys.modules
```
