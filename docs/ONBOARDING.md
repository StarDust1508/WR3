# wr3 — Onboarding checklist

Что нужно зарегистрировать / настроить **руками** перед первым полным проходом аудита.
Всё бесплатное на бесплатных тирах (см. [TZ.md §3, §15](../TZ.md)). По возможности — без юр.лица; NM LLC откладывается до месяца 4+.

Порядок имеет значение. Делать сверху вниз.

---

## 1. Локальное окружение разработчика

### Базовые инструменты

| Tool | Версия | Установка |
|---|---|---|
| Bun | ≥ 1.2 | `curl -fsSL https://bun.sh/install \| bash` |
| uv | ≥ 0.10 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Postgres 16 (native) | Homebrew | `brew install postgresql@16 && brew services start postgresql@16` |
| Redis (native) | Homebrew | `brew install redis && brew services start redis` |
| Foundry (forge/anvil/cast) | актуальная | `curl -L https://foundry.paradigm.xyz \| bash && foundryup` |
| Aderyn | актуальная | `cargo install aderyn` либо binary с https://github.com/Cyfrin/aderyn/releases |
| Wake | актуальная | `uv tool install eth-wake` |
| Slither | актуальная | `uv tool install slither-analyzer` |
| Medusa | актуальная | binary с https://github.com/crytic/medusa/releases |
| Trident (Solana) | актуальная | `cargo install trident-cli` |
| Docker Desktop | опционально | https://docker.com — только для Anvil sandbox / vLLM |

**Native Postgres + Redis обязательны.** Docker используется только для опциональных профилей (`--profile sandbox`, `--profile gpu`, `--profile fallback`).

### Bootstrap одной командой

```bash
bash scripts/native-setup.sh
```

Идемпотентно: создаёт базу `wr3`, ставит `vector` / `uuid-ossp` / `pg_trgm` расширения, гарантирует что сервисы запущены, копирует `.env.example` → `.env.local`.

Если у тебя в Redis настроен `requirepass`, вставь пароль в `REDIS_URL` в `.env.local` (формат: `redis://:PASSWORD@localhost:6379/0`).

### Применить миграции

```bash
cd apps/api
DATABASE_URL=postgresql+psycopg://localhost:5432/wr3 uv run alembic upgrade head
```

После — должны появиться таблицы `scans`, `findings`, `alembic_version`:
```bash
psql -d wr3 -c "\dt"
```

### Проверка установки

```bash
bun --version && uv --version && forge --version
psql -V && redis-cli -a "$REDIS_PASSWORD" ping 2>/dev/null || redis-cli ping
aderyn --version && wake --version && slither --version
medusa --version
```

---

## 2. Аккаунты на бесплатных сервисах

Для каждого — зарегистрироваться, получить ключ, записать в `.env.local`.

### Обязательные для MVP

1. **GitHub** ([github.com](https://github.com)) — репозиторий уже создан: `StarDust1508/WR3`. Дать доступ trusted-членам команды.
2. **OpenRouter** ([openrouter.ai](https://openrouter.ai)) — основной LLM-роутер для security-чувствительных вызовов с `zdr:true`. Депонировать $10, чтобы поднять лимит до 1000 RPD на free-модели.
3. **api.navy** ([api.navy](https://api.navy)) — для UI/coding-glue. Free tier 150K токенов/день.
4. **Google Cloud / AI Studio** ([aistudio.google.com](https://aistudio.google.com)) — Gemini API key для embeddings. **Не использовать для security-промптов** (free tier prompts идут на тренинг).
5. **Etherscan API key** ([etherscan.io/apis](https://etherscan.io/apis)) — для pull верифицированного исходника.
6. **BscScan / Basescan / Arbiscan** — отдельные API keys, free tier на каждом эксплорере.
7. **Alchemy** ([alchemy.com](https://alchemy.com)) — primary RPC. 300M CU/мес бесплатно.
8. **Telegram BotFather** ([t.me/BotFather](https://t.me/BotFather)) — `/newbot`, получить токен. Имя бота можно `@wr3_audit_bot` (проверить доступность).
9. **Cloudflare** ([dash.cloudflare.com](https://dash.cloudflare.com)) — Workers + D1 + R2 + Registrar. Регистрируем домен (~$10/год).

### После W2 (heavy backend)

10. **Oracle Cloud Always Free** ([oracle.com/cloud/free](https://oracle.com/cloud/free)) — `Ampere A1 Flex`, 4 OCPU + 24GB RAM + 200GB storage. **Pитфолы**:
    - В популярных регионах часто "out of capacity" — пробовать Frankfurt / Phoenix / Singapore, ставить ретрай-скрипт.
    - Если CPU <20% за 7 дней — могут reclaim инстанс. Держать реальную нагрузку (Postgres + Redis уже это обеспечат).
    - Аккаунт могут suspend без warning — обязательно делать daily-backup в R2.
    - **Карту** нужно привязать, но списываний нет (только верификация).
11. **Doppler** ([doppler.com](https://doppler.com)) — secrets management. Free tier 10 secrets × 5 envs. Альтернатива на старте — `.env.local` с .gitignore.

### После W12 (monitoring)

12. **Sentry** ([sentry.io](https://sentry.io)) — error tracking. Free 5k errors/мес.
13. **UptimeRobot** ([uptimerobot.com](https://uptimerobot.com)) — 50 monitors free, 5min interval.
14. **BetterStack** ([betterstack.com](https://betterstack.com)) — logs (3GB/мес).

### После W19 (payments, опционально)

15. **Request Finance** ([request.finance](https://request.finance)) — B2B crypto invoicing.
16. **Polar.sh** ([polar.sh](https://polar.sh)) — fiat MoR без юр.лица (4% fee).
17. **TON Connect** ([docs.ton.org/develop/dapps/ton-connect](https://docs.ton.org/develop/dapps/ton-connect)) — TON wallet integration в Mini App.
18. **(Месяц 4+)** New Mexico LLC через [NorthwestRegisteredAgent.com](https://northwestregisteredagent.com) — $50 filing + $125 agent. EIN бесплатно через IRS Form SS-4. Mercury bank.

---

## 3. Bootstrap-проверки после установки

После заполнения `.env.local`:

```bash
# 1. Postgres + Redis уже запущены через brew services (см. шаг 1).
brew services list | grep -E "postgresql|redis"

# 2. Bun workspace
bun install

# 3. Audit engine tests
cd packages/audit-engine
uv sync
uv run pytest -q                               # 9 passed

# 4. API + migrations + smoke
cd ../../apps/api
uv sync
DATABASE_URL=postgresql+psycopg://localhost:5432/wr3 uv run alembic upgrade head
uv run pytest -q                               # 2 passed
uv run uvicorn wr3_api.main:app --reload --port 8001 &
sleep 2
curl -s http://localhost:8001/v1/health        # {"status":"ok"}
curl -s -X POST http://localhost:8001/v1/scan \
  -H 'Content-Type: application/json' \
  -d '{"address":"0x1111111111111111111111111111111111111111","network":"base","source_code":"contract A {}"}'
psql -d wr3 -c "SELECT address, network, stage FROM scans ORDER BY created_at DESC LIMIT 1;"
kill %1

# 5. Web smoke
cd ../web
bun install
bun run dev &
sleep 3
curl -s http://localhost:3000 | head -20       # должен вернуть HTML
kill %1
```

Если что-то падает — баг в коде, фикcить, не пропускать.

---

## 4. Что НЕ делать на этом этапе

- ❌ Не подавать в Anthropic Cyber Verification Program — мы намеренно идём через OpenRouter ZDR (см. TZ.md §4.2).
- ❌ Не оформлять Stripe Atlas ($500) — NM LLC через NorthwestRegisteredAgent дешевле в 3x.
- ❌ Не покупать PI insurance — SEAL Legal Defense Fund + Safe Harbor agreements закрывают (TZ.md §3.4).
- ❌ Не деплоить anywhere до W14 closed beta.
- ❌ Не использовать Telegram Stars для платежей — 32% fee убивает unit-economics.

---

## 5. Чек-лист готовности к W2

Перед началом второй недели должны быть:

- [ ] `.env.local` заполнен ключами (минимум OpenRouter, NavyAI, Etherscan, Alchemy)
- [ ] `docker compose ps` показывает healthy Postgres + Redis
- [ ] `uv run pytest` в audit-engine — зелёный
- [ ] `curl http://localhost:8001/v1/health` — `{"status":"ok"}`
- [ ] `bun run dev` в `apps/web` — открывается на localhost:3000
- [ ] Telegram bot token получен (для W11)
- [ ] Aderyn + Wake + Slither + Foundry установлены глобально и `--version` работает
- [ ] GitHub repo приватный, branch protection на `main` включён, signed commits required

После — стартует W2: ingestion + первый Aderyn-проход (см. TZ.md §11 Phase 1).
