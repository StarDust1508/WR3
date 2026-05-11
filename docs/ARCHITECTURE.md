# wr3 Architecture — pointer file

Полная архитектура: [TZ.md](../TZ.md).

## Quick map

| Что | Где в TZ |
|---|---|
| 7-layer pipeline overview | §4.1 |
| Orchestration (Claude Agent SDK + custom DAG) | §4.2 |
| Knowledge base / RAG sources | §4.3 |
| Cherry-pick from Aether | §4.4 |
| Benchmark targets (EVMbench, Trident Arena) | §4.5 |
| Full tech stack matrix | §5 |
| Blockchain priority | §6 |
| UX (web + Mini App) | §7 |
| Scoring system | §8 |
| News + on-chain monitoring | §9 |
| OpSec | §10 |
| MVP weekly plan (W1–W20) | §11 |
| Risk register | §14 |

## Repo map

```
apps/
  web/                     Next.js 15 (App Router, Turbopack, Tailwind 4)
    app/                   Routes: /, /scan, /leaderboard, /pricing, /docs, /auth
    components/            UI primitives + features
    lib/                   Utilities (cn, fetchers)
  api/                     FastAPI gateway + Celery workers
    src/wr3_api/
      main.py              ASGI app
      config.py            pydantic-settings (env-driven)
      routes/              health, scan, (auth, billing — W10+)
      workers/             Celery tasks orchestrating audit_engine
      models/              SQLAlchemy models (W3+)
    tests/                 pytest

packages/
  audit-engine/            Core audit pipeline (Python, importable by api)
    src/audit_engine/
      pipeline.py          7-stage orchestrator yielding PipelineEvent
      analyzers/           Aderyn, Wake, Slither (subprocess wrappers)
      agents/              Multi-agent triage (Trident Arena pattern)
      llm/                 Router by sensitivity (LOW/MEDIUM/HIGH/SECRET)
      reports/             Markdown / PDF rendering
      scoring.py           5-axis weighted scoring
      types.py             Pydantic Finding / ScoreAxis / AuditReport
    tests/                 pytest

  shared/                  TS types mirroring audit_engine.types
    src/index.ts

scripts/
  init-db.sql              Postgres extensions + roles bootstrap
```

## License isolation

Pipeline orchestration (wr3 IP) is proprietary. GPL/AGPL tools — Aderyn (GPL-3),
Slither (AGPL-3), Medusa (AGPL-3), Halmos (AGPL-3), Echidna (AGPL-3), Certora
Prover (GPL-3) — are invoked **only as subprocesses with JSON I/O**. They are
NOT linked as libraries. This keeps wr3's core SaaS code outside copyleft scope.

Permissive deps (linkable):
- **Wake** (ISC) — can import as Python library
- **ItyFuzz** (MIT)
- **Trident** (Apache 2.0)
- **Foundry** (MIT/Apache dual)
- **Aether seed data** (MIT) — cherry-picked exploit_patterns.json, historical_exploits.json

## Engine versions tracked

The `AuditReport.engine_versions` dict captures versions of every tool used in a
specific audit. This is critical for:
- Reproducing historical audits when a new finding class is added
- Defending against negligence claims ("which Aderyn version was used? did it
  have the relevant detector at the time?")
- Public benchmark consistency

Always populate this before emitting `done`.
