# wr3

AI-platform for smart contract auditing in the $200–2000/audit niche — vibe-coders and small teams on **BSC / Base / Arbitrum / Ethereum / Solana**.

Full spec: [TZ.md](TZ.md).

## Stack at a glance

| Layer | Choice |
|---|---|
| Frontend | Next.js 15, Tailwind 4, shadcn/ui |
| Backend | FastAPI + Celery (Python 3.13, uv) |
| Audit engine | Aderyn + Wake + Slither (EVM static) · Medusa + ItyFuzz + Foundry invariant · Trident (Solana) · Certora Prover (formal, premium) · Halmos (symbolic, opt) |
| AI orchestration | Claude Agent SDK + custom DAG |
| LLM routing | OpenRouter (`zdr:true`) for security PoC · api.navy for UI · Qwen3-Coder 30B-A3B local fallback |
| Knowledge base | Solodit API · DeFiHackLabs · Sealevel-attacks · DAppSCAN · SWC Registry |
| DB | Postgres 17 + pgvector · Redis · Cloudflare D1 (edge) · R2 (objects) |
| Hosting | Cloudflare Workers (edge) + Oracle Always Free (heavy backend) |
| Payments | USDC EOA + Request Finance · TON Connect · Polar.sh fallback · Stripe (later, NM LLC) |

## Repo layout

```
wr3/
├─ apps/
│  ├─ web/                 Next.js 15 — public site, dashboard, Mini App
│  └─ api/                 FastAPI — API gateway, Celery workers
├─ packages/
│  ├─ audit-engine/        Audit pipeline (Python): analyzers, agents, LLM router, reports
│  └─ shared/              TS types shared between web and api
├─ scripts/                Bootstrap, migrations, fixtures
├─ docs/
│  ├─ ONBOARDING.md        External setup checklist (Oracle, Cloudflare, RPC keys, etc.)
│  └─ ARCHITECTURE.md      Pointer to TZ.md sections
├─ docker-compose.yml      Postgres (pgvector) + Redis + optional Anvil/vLLM
├─ turbo.json              Turborepo task pipeline
└─ TZ.md                   Full technical specification
```

## Quickstart (local dev)

Prerequisites: [Bun](https://bun.sh) ≥ 1.2, [uv](https://docs.astral.sh/uv/) ≥ 0.5, [Docker](https://docker.com), [Foundry](https://book.getfoundry.sh/) (optional for PoC sandbox).

```bash
# 1. Clone & install
git clone https://github.com/StarDust1508/WR3.git wr3
cd wr3
cp .env.example .env.local
# Fill in keys from docs/ONBOARDING.md

# 2. Start Postgres + Redis
docker compose up -d postgres redis

# 3. Web (Next.js)
cd apps/web
bun install
bun run dev               # http://localhost:3000

# 4. API (FastAPI)
cd ../api
uv sync
uv run uvicorn wr3_api.main:app --reload   # http://localhost:8001

# 5. Audit engine (used as library by api)
cd ../../packages/audit-engine
uv sync
uv run pytest             # baseline tests
```

## What you need to do externally

See [docs/ONBOARDING.md](docs/ONBOARDING.md). Short version:

1. Sign up for **Oracle Cloud Always Free** (production backend, 4 OCPU + 24GB free forever)
2. Cloudflare account + create Workers/Pages, D1 DB, R2 bucket
3. OpenRouter account (get $10 credit → 1000 RPD with `zdr:true`)
4. api.navy account (free 150K tokens/day)
5. Alchemy free tier (300M CU/month)
6. Telegram bot token via [@BotFather](https://t.me/BotFather)
7. (Optional, month 4+) New Mexico LLC + Mercury bank for fiat payments

## Roadmap

W1–W14 closed beta, W15–W20 public launch. Detailed weekly plan in [TZ.md §11](TZ.md#11-план-mvp-по-неделям-14-недель-до-closed-beta--6-недель-до-public).

## License

Source code: see individual `LICENSE` per package. Pipeline orchestration is proprietary; tool integrations (Aderyn GPL-3, Slither AGPL-3, Medusa AGPL-3, Halmos AGPL-3, Certora GPL-3) are invoked via subprocess to maintain license isolation.
