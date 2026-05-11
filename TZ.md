# wr3 — Техническое задание

**Версия:** 1.0  
**Дата:** 2026-05-11  
**Автор:** составлено в соавторстве с Claude Opus 4.7 после 6 параллельных раундов ресёрча  
**Репозиторий:** https://github.com/StarDust1508/WR3

---

## 0. Executive summary

**wr3** — AI-платформа автоматического аудита смарт-контрактов с фокусом на нишу **vibe-кодеров и команд 1-5 человек на BSC / Base / Arbitrum / Ethereum / Solana**, чей бюджет на security меньше $2000 и которые не могут позволить себе CertiK ($25k+/неделя) или Hacken ($5-50k/аудит).

Дифференциация: (1) **гибрид статического анализа + LLM-триажа + Foundry-PoC + AI-фуззинга** в одном пайплайне, что не делает ни один SaaS открыто; (2) **Solana-аудит как первоклассный фронт** — никто из open-source не покрывает Solana всерьёз; (3) **прозрачное scoring 0-100 + светофор с публичными весами** против CertiK-black-box и pay-to-play Skynet; (4) **distribution через Telegram-бот / Mini App + web** — там, где живёт ЦА (BSC vibe-кодеры в TG-чатах, BNB Chain Discord 314k).

Финансовая цель: **$1-10k MRR через 90 дней после public launch (≈месяц 7-8 от старта)**. Юр.лицо — **New Mexico LLC $150** или **без юр.лица** на bootstrap-фазе через USDC + Request Finance. Команда — 3 человека + AI-агенты. Бюджет MVP — **$200-1500 CAPEX + $0-100/мес OPEX** (всё на бесплатных тирах).

Бенчмарк качества: **превзойти Trident Arena (70% recall на 30 known Solana CVEs)** и держаться в верхней половине EVMbench (OpenAI/Paradigm) против GPT-5.3-Codex baseline.

Правовая модель: **только passive disclosure (responsible disclosure 7/14/45/90/180-дневные ворота) + активные действия исключительно для проектов в SEAL Whitehat Safe Harbor V3 registry**. Никакого «взлома сети, чтобы заметили» — это уголовка во всех целевых юрисдикциях.

---

## 1. Vision и философия

### 1.1. Зачем мир нуждается в wr3

Big-3 (CertiK / Hacken / Trail of Bits) обслуживают топ-100 протоколов и пропускают «длинный хвост» — ~90% pre-launch проектов на BSC / Base / Solana, которые делают vibe-кодеры с AI-сгенерированным кодом. Эти проекты теряют деньги пользователей и подрывают доверие ко всей экосистеме крипты.

Реальные провалы big-3 за 2023-2026 (документация для маркетинга wr3):

- **Merlin DEX, апрель 2023** — $1.8M rugpull. CertiK провёл аудит, упомянул centralization risks мелким шрифтом, потом заморозил только $160k.
- **Hacken HAI, июнь 2025** — собственный bridge Hacken между Ethereum и BSC был скомпрометирован через утечку приватного ключа. Минт ~900M HAI на обеих сетях, ~$250k вытащено, токен упал на 98-99%. **Аудитор не смог защитить себя.**
- **Balancer V2, ноябрь 2025** — $121M через 4 audit-firm, которые пропустили баг. Olympix постфактум писал «мы бы поймали, если бы нас использовали».
- **Euler $197M (март 2023)**, **Wormhole $326M (февраль 2022)**, **Ronin $625M (март 2022)** — все прошли множественные аудиты.

### 1.2. Гипотеза, на которой строится wr3

«Большая часть крипто-проектов на длинном хвосте созданы AI, значит у них есть паттерн, значит для нас прибыль» — формулировка владельца.

Это **подтверждается** ресёрчем:
- BSC доминировал по числу rugpulls в 2024-2025 (Chainalysis)
- Base в мае 2025 пробил 5M daily contract deployments (Nansen)
- Cluster Protocol / CodeXero привлекли $5M в апреле 2026 на «vibe-coding IDE для EVM прямо из браузера» — деньги идут в эту нишу именно сейчас
- 94% долгоиграющих bounty-программ уже нашли critical bug — низко висящие фрукты сняты с топ-уровня, но не с длинного хвоста

### 1.3. Что wr3 НЕ делает

- **Не атакует проекты без явной авторизации.** Это уголовка во всех целевых юрисдикциях (US CFAA, UAE Decree-Law 34/2021 — нет good-faith exception, RU УК ст.272, KZ ст.205).
- **Не делает «hack-and-rescue».** Mango Markets/Eisenberg-прецедент не покрывает: его оправдали по узкому wire-fraud составу, prosecutors подали апелляцию, решение не вступило окончательно.
- **Не позиционирует AI как замену human auditor.** AI-assisted = enhancement, не replacement. Это и юридическая защита от negligence-claim.
- **Не публикует «X is scam» без manual review** (defamation risk).

---

## 2. Позиционирование

### 2.1. Сегментация

**Primary ICP:** solo-разработчики и команды 2-5 человек, деплоящие AI-сгенерированный код на BSC / Base / Arbitrum / Ethereum L1 / Solana. Бюджет на security $200-2000 / audit. Боль: «я задеплоил, у меня TVL $50k, я не сплю по ночам».

**Where they live:**
- [BNB Chain Discord](https://discord.com/invite/bnbchain) — 314k членов
- [@BNBchaincommunity](https://t.me/BNBchaincommunity), @BNBChainDevs в TG
- X/Twitter Base-кластер
- TG-чаты типа «Hardhat», «Foundry», «Anchor Solana»
- Farcaster — депонизирован (<20k MAU в конце 2025), вторичный канал

**Secondary ICP (roadmap, не MVP):** держатели токенов, которые перед покупкой проверяют Security Score проекта (как Skynet, но прозрачно).

### 2.2. Конкурентная карта (май 2026)

| Игрок | Цена | Ниша | Состояние | Угроза для wr3 |
|---|---|---|---|---|
| **CertiK** | $5k-$50k | Top-100 | Жив, репутация подмочена | Низкая — другая лига |
| **Hacken** | $5k-$50k | Top-200 | Жив, HAI скандал ослабил | Низкая |
| **Trail of Bits** | $25k+/week | Enterprise | Жив, AI-augmented через Claude | Низкая |
| **Olympix** | $149/dev + enterprise | Solo-devs через VS Code | Жив, closed-source | **Высокая** — ближе всех по vision |
| **Cantina** | Enterprise | Top-tier protocols + AI co-pilot | Series A $7.83M | Низкая |
| **Sherlock AI V2** | Контест-based | Mid-large | Активен | Низкая |
| **Sec3 X-Ray** | Enterprise (closed) | Solana | Жив | Средняя на Solana |
| **L3X** | Closed | Solana | Низкая видимость | Средняя |
| **ChainGPT AI Auditor** | $0.01/scan | Mass-market low-quality | Жив | **Низкая, но забирает дешёвый сегмент без trust** |
| **Cluster Protocol / CodeXero** | Freemium IDE | Vibe-coders на EVM | $5M raise апр 2026 | **Прямой конкурент в эту нишу** |
| **Matterhorn (ASI)** | Tooling | Vibe-coding security | Запущен апр 2026 | Средняя |
| **Trail of Bits + Claude Skills** | Free | Все Claude-юзеры | Live | Косвенная — повышает baseline |

**Окно для wr3:** ниша $200-2000 для solo/small teams **реально пустая**. ChainGPT не воспринимается всерьёз (no trust), CodeXero — IDE, не standalone audit, Matterhorn — tooling. Окно закроется к концу Q3 2026, когда зайдут 5-10 хорошо профинансированных стартапов.

### 2.3. Дифференциация (4 моата)

1. **Solana-аудит как первоклассный фронт.** Aether/Olympix/ChainGPT — EVM only. Sec3 X-Ray и L3X — closed. wr3 единственный объединяет EVM + Solana с публичной архитектурой.
2. **Telegram Mini App + bot как acquisition-канал.** Big-3 туда не идут. ICP — там.
3. **Transparent scoring с публичными весами** против CertiK Skynet black-box. Анти-pay-to-play.
4. **Public benchmark на DefiHackLabs (689 incidents) + EVMbench.** Никто такого открыто не публикует. Это и legitimacy, и marketing-актив.

---

## 3. Стратегия монетизации и операций

### 3.1. Источники revenue (приоритет)

| # | Канал | Старт | Цель Y1 |
|---|---|---|---|
| 1 | Paid subscriptions team-tier ($29/$99/$499/мес) | Месяц 3 | $3-7k MRR |
| 2 | One-shot audit reports ($200-2000) | Месяц 4 | $1-3k MRR equivalent |
| 3 | Audit-контесты как individual whitehat через Hats Finance / CodeHawks / Cantina | Месяц 1 (без юр.лица) | $500-3k/мес irregular |
| 4 | Forta v2 detection bots subscriptions | Месяц 5 | $200-1000/мес (не основной) |
| 5 | Bounty splits для Safe Harbor проектов | Месяц 6+ | spike-revenue, не reliable |
| 6 | API-access / programmatic для других платформ | Roadmap Y2 | — |

**Tier-структура SaaS:**
- **Free**: 1 контракт / 24h, preliminary score только, без PoC
- **Hobby $29/мес**: 10 контрактов/мес, mid-detail report, Telegram alerts
- **Team $99/мес**: unlimited контракты, full report с Foundry PoC, Slack/Discord webhook
- **Pro $499/мес**: + continuous monitoring 24/7, custom invariants, Safe Harbor onboarding helper

Mid-tier $29 критичен — он закрывает пропасть между free и $99 для индивидуальных vibe-кодеров.

### 3.2. Платежи (без юр.лица на старте)

| Канал | Использование |
|---|---|
| **USDC EOA на Base/Arbitrum** | Primary для крипто-клиентов. 0% fees ($0.01 gas). |
| **[Request Finance](https://request.finance/)** | B2B invoicing в крипте, ~0.1% gas. Для DAO/протоколов. |
| **[Polar.sh](https://polar.sh/)** | MoR для fiat без юр.лица. 4% + $0.40. |
| **[Lemon Squeezy](https://lemonsqueezy.com/)** | Альтернатива Polar. 5% + 50¢. |
| **TON Connect через Mini App** | Для TG-пользователей с TON wallet. ~0% fees после октября 2025. |
| **Stripe + NM LLC** | Когда выручка стабильно $5k+/мес. $150 setup. |

**НЕ использовать:** Telegram Stars (32% fee = убийца unit-economics для $200-2000), Stripe Atlas ($500 за то, что можно сделать самим за $150).

### 3.3. Юридическая структура

**Фаза 1 (месяцы 1-3, $0):** без юр.лица, доход через USDC EOA + Request Finance. Декларация — в стране резидентства каждого участника.

**Фаза 2 (месяцы 4-6, $150):** New Mexico LLC. $50 filing, $35-100/год registered agent (NorthwestRegisteredAgent.com), EIN бесплатно через IRS form SS-4. Mercury / Relay banking. Подключение Stripe.

**Фаза 3 (Y2, опционально):** если оборот $50k+/мес и нужен audit-trail для enterprise-клиентов — DIFC Innovation License ($1500/год, common law jurisdiction). До этого момента DIFC overkill.

### 3.4. Юридическая защита

- **[SEAL Whitehat Safe Harbor V3.0](https://github.com/security-alliance/safe-harbor)** — все активные действия (PoC, fork-эксплуатация) только для проектов из реестра (Uniswap, Aave, Balancer, Pendle, PancakeSwap, zkSync, Silo, Lido, Polymarket, ENS, Inverse, Origin, Alchemix и др. на май 2026).
- **[SEAL Legal Defense Fund](https://www.bitsofblocks.io/post/seal-launches-legal-defence-fund-for-whitehats)** — funded a16z / Paradigm / Electric Capital / EF / Filecoin Foundation. Покрывает legal fees при добросовестном disclosure. Замена PI insurance частичная (не покрывает damages).
- **Explicit disclaimer в TOS + каждый findings-репорт:** «AI-assisted audit, not a replacement for human review, no warranty, cap of liability = cost of audit».
- **Engagement letter** для каждого paid-audit перед началом работ. Шаблон — общий с TOS, custom-добавки по запросу клиента.

### 3.5. Эскалация при игнорировании находки

Стандарт responsible disclosure:

- Day 0-7: private contact (3 канала параллельно — email, TG-founder, security@).
- Day 7-14: эскалация через **SEAL 911** (24/7 Telegram-хаб с trusted whitehats).
- Day 14-45: уведомление **MITRE CVE** / **ENISA EUVD**.
- Day 90: limited disclosure (класс бага, без working PoC).
- Day 180: full PoC если фикса нет.

Никогда — публичный broadcast эксплойта без disclosure-окна. Никогда — активная атака на сеть. Это и юр.требование, и условие легитимности у клиентов.

---

## 4. Архитектура AI-движка

### 4.1. Высокоуровневый pipeline

```
Input: contract address / source code / Etherscan-verified
   │
   ▼
[Layer 1] Source ingestion & normalization
   - Verified source pull (Etherscan / BscScan / Basescan / Arbiscan / Solana Explorer)
   - AST parsing (solc / anchor-syn)
   - Bytecode disassembly fallback (если source не verified)
   │
   ▼
[Layer 2] Multi-engine static analysis (parallel)
   - Aderyn (EVM, GPL-3, CLI subprocess)
   - Wake (EVM, ISC, library)
   - Slither (EVM, AGPL, CLI fallback)
   - Custom AST analyzer for Solana (anchor-syn-based)
   │
   ▼
[Layer 3] LLM triage (multi-agent, по паттерну Trident Arena)
   - Agent A: Severity classifier (ранжирует raw findings)
   - Agent B: False-positive filter (читает context, отсеивает шум)
   - Agent C: Business logic reasoner (ищет логические баги, не паттерны)
   - Agent D: Cross-contract analyzer
   - Cross-check / consensus (ноды договариваются)
   │
   ▼
[Layer 4] PoC generation (Foundry retry-loop)
   - LLM пишет тест на Solidity
   - forge test --fork-url --json
   - На revert/error: LLM читает trace и адаптирует
   - До 5 попыток на finding
   - Solana: Trident harness generation + anchor test
   │
   ▼
[Layer 5] AI-fuzzing with generated invariants
   - LLM генерирует invariant_*() functions
   - Medusa (EVM, AGPL, subprocess) или Foundry invariant (built-in)
   - ItyFuzz для hybrid concrete+symbolic
   - Trident для Solana
   - Recon Chimera-templates как scaffolding
   │
   ▼
[Layer 6] Formal verification (опционально, premium tier)
   - Certora Prover (open-source GPL-3, EVM + Solana + Stellar)
   - Halmos для symbolic exec в Foundry-тестах
   │
   ▼
[Layer 7] Scoring & reporting
   - 0-100 + светофор
   - 5 осей с публичными весами
   - Markdown / PDF report
   - Optional: SARIF для CI/CD интеграции
   │
   ▼
Output: structured report + dashboard + alerts
```

### 4.2. Оркестрация агентов

- **Runtime:** [Claude Agent SDK](https://docs.anthropic.com/claude-agent-sdk) + **кастомный DAG** поверх (паттерн Aether / PentestGPT, не LangGraph).
- **LLM-роутинг:** через **[OpenRouter](https://openrouter.ai/)** с `zdr: true` для security-чувствительных промптов. **api.navy** только для UI / coding-обвязки (security work через NavyAI — нет, retention не подтверждён).
- **Локальная модель fallback:** **[Qwen3-Coder 30B-A3B](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct)** (Apache 2.0, 77.2% SWE-Bench Verified) на RTX 4090 (Q5_K_M) через **vLLM**. ~73 tok/s на 4090.
- **Memory / blackboard:** Postgres + pgvector с pheromone-decay паттерном (из Pentest-Swarm-AI). Long-running audit-сессии не захлёбываются в кандидатах.
- **MCP server `wr3-mcp`:** агрегирует все tools (Aderyn / Wake / Medusa / ItyFuzz / Trident / Certora / Foundry / Solodit API) — единая точка для AI-агента. Архитектурный референс: [Slither MCP от Trail of Bits](https://github.com/trailofbits/slither-mcp).

### 4.3. Knowledge base / RAG

| Источник | Что | Использование |
|---|---|---|
| [Solodit API (Cyfrin)](https://solodit.cyfrin.io/) | 50K+ findings от ToB / OZ / Sherlock / Code4rena | Primary RAG knowledge base |
| [DeFiHackLabs](https://github.com/SunWeb3Sec/DeFiHackLabs) | 689 incidents с Foundry PoC | Training corpus, PoC-replay |
| [Sealevel-attacks](https://github.com/coral-xyz/sealevel-attacks) | 13 категорий Solana-атак, insecure/recommended pairs | Solana golden dataset |
| [DAppSCAN](https://github.com/InPlusLab/DAppSCAN) | 39,904 Solidity файлов, 1,618 SWC weaknesses | Large-scale embed corpus |
| [SmartBugs Curated](https://github.com/smartbugs/smartbugs-curated) | 143 контракта с labeled vulnerabilities | Benchmark suite |
| [SWC Registry](https://swcregistry.io/) | 37 классических weaknesses | Taxonomy ID |
| Rekt News (скрейп) | Markdown post-mortems | Hack stories для AI-context |
| Helius Solana hacks blog | Структурированный Solana-incidents log | Solana history RAG |
| Aether seed data (cherry-pick) | 75 exploit patterns + 20 hist exploits + 14 archetypes | Bootstrap pattern library |

Embeddings — **Gemini embedding** через [text-embedding-gemini](https://ai.google.dev/gemini-api/docs/embeddings) ($0.000025/1k токенов, free tier 100 RPM). Дёшево, качество достаточное.

### 4.4. Cherry-pick из [Aether v6.0](https://github.com/l33tdawg/aether) (MIT)

НЕ форкать целиком (bus-factor 1, 80% Claude-generated code, SAGE hard-dependency). Взять конкретно:

- `core/foundry_poc_generator.py` (4058+ строк) — PoC-генерация и `forge test --json` retry-loop
- `data/sage_seeds/exploit_patterns.json` — 75 паттернов как seed knowledge
- `data/sage_seeds/historical_exploits.json` — 20 кейсов (DAO, Wormhole, Euler, Ronin, Curve)
- Структура 14 protocol archetypes
- Halmos-runner integration pattern (`tests/test_halmos_runner.py` как референс)
- Multi-pass pipeline идея с **dismissal-as-first-class-record** (Pass-3 dismissed → Pass-5 не re-flag)

Бюджет: 2-3 недели на изучение и интеграцию. Attribution в README обязательно (MIT требует).

### 4.5. Бенчмарк целей

**Внешние:**
- **[EVMbench](https://openai.com/index/introducing-evmbench/) (OpenAI/Paradigm)** — публичный leaderboard на Code4rena. GPT-5.3-Codex решает 70% critical bugs. wr3 цель: ≥50% Codex-baseline на MVP, ≥80% на v1.0.
- **Trident Arena (Ackee)** — 70% recall на 30 known Solana CVEs, FP rate 26%. wr3 цель на Solana: ≥75% recall, FP <30%.

**Свой публичный leaderboard wr3 на DefiHackLabs:**
- 100 случайных incidents → wr3 vs Slither / Aderyn / Olympix-публичные / Trident-Arena
- Метрики: precision / recall / F1 / time-to-detect
- Публикация раз в квартал в [wr3-bench](https://github.com/StarDust1508/WR3) репозитории
- Это marketing-актив + legitimacy. Никто открыто такого не делает.

---

## 5. Tech stack — подробно

### 5.1. Frontend

| Компонент | Решение | Лицензия |
|---|---|---|
| Web app | Next.js 15 (App Router) | MIT |
| UI library | Tailwind 4 + shadcn/ui | MIT |
| Charts | Recharts / Visx | MIT |
| Wallet auth | SIWE (ethereum) + TON Connect (Solana через Wallet Adapter optional) | MIT |
| TG Mini App | `@telegram-apps/sdk` v3 | MIT |
| State | TanStack Query + Zustand | MIT |

### 5.2. Backend

| Компонент | Решение | Лицензия |
|---|---|---|
| API | Python 3.13 + FastAPI | MIT |
| Blockchain client | Node.js + viem (TS) для EVM, web3.js для Solana | MIT |
| Queue | Celery + Redis (Postgres-backed Celery beat для cron) | BSD-3 |
| Auth | NextAuth v5 (web) + custom JWT для Mini App via initData | MIT |
| LLM router | Claude Agent SDK + custom DAG | MIT |
| Audit tools wrappers | Slither/Aderyn/Wake/Medusa/ItyFuzz/Trident — subprocess | varies |

### 5.3. Database & storage

| Слой | Стек | Free? |
|---|---|---|
| Hot edge DB | [Cloudflare D1](https://developers.cloudflare.com/d1/) | 5GB / 5M reads / 100k writes |
| Primary DB | self-hosted Postgres 17 на Oracle Always Free Ampere VM | $0 forever |
| Vector store | pgvector extension | $0 |
| Object storage | [Cloudflare R2](https://developers.cloudflare.com/r2/) (отчёты PDF) | 10GB free + 1M class A ops |
| Cache | Redis на Oracle VM | $0 |

### 5.4. Infrastructure

| Слой | Решение | Стоимость |
|---|---|---|
| Edge API | [Cloudflare Workers](https://developers.cloudflare.com/workers/) | 100k req/день free |
| Heavy backend | Oracle Cloud Always Free (4 OCPU ARM + 24GB RAM + 200GB) | $0 forever |
| GPU для self-hosted LLM | RTX 4090 (друг даёт) или vast.ai $0.30/час on-demand | ~$0-50/мес |
| RPC primary | Alchemy 300M CU/мес | Free tier |
| RPC fallback | drpc.org + PublicNode + Ankr public | Free unlimited (per-IP rate-limit) |
| Domain | Cloudflare Registrar | ~$10/год |
| Email transactional | Resend free tier (100/день) или Cloudflare Email Workers | Free |
| CI/CD | GitHub Actions (2000 min/мес private, unlimited public) | Free |
| Monitoring | Sentry free (5k errors/мес) + UptimeRobot (50 monitors) + Telegram bot | $0 |
| Secrets | Doppler free (10 secrets, 5 envs) | $0 |

### 5.5. AI providers — routing strategy

| Сценарий | Провайдер | Зачем |
|---|---|---|
| UI / ассистент / coding-обвязка | api.navy (NavyAI) | Дёшево, удобный single endpoint, retention неважен |
| Генерация PoC эксплойтов | OpenRouter с `zdr:true` → DeepSeek V3.2 / Qwen3-Coder | Официальный ZDR, security-чувствительно |
| Финальный reasoning над findings | OpenRouter `zdr:true` → Claude Sonnet 4.6 / Opus 4.7 | Лучшее качество reasoning |
| Локальный fallback для самых чувствительных данных | Qwen3-Coder 30B-A3B на RTX 4090 (vLLM) | Полная приватность |
| Embeddings | Gemini text-embedding | $0.000025/1k токенов |
| Голосовая/мультимодальная | Не нужно для MVP | — |

**Бюджет LLM в MVP:** $0-100/мес (free tiers + Qwen локально покрывают 80% запросов). При росте — pay-per-use, scales with revenue.

### 5.6. Static analysis tools

| Tool | Лицензия | Платформа | Использование |
|---|---|---|---|
| **[Aderyn](https://github.com/Cyfrin/aderyn)** | GPL-3 | EVM | Primary, через CLI subprocess |
| **[Wake](https://github.com/Ackee-Blockchain/wake)** | ISC | EVM | Secondary, можно линковать как library |
| **[Slither](https://github.com/crytic/slither)** | AGPL-3 | EVM | Fallback для legacy v0.4/0.5, через CLI |
| Custom AST Solana | wr3 own, MIT | Solana | Single primary (нет open-source альтернативы) |

### 5.7. Fuzzing tools

| Tool | Лицензия | Платформа | Использование |
|---|---|---|---|
| **[Medusa](https://github.com/crytic/medusa)** | AGPL-3 | EVM | Primary, через subprocess (5-7x быстрее Echidna) |
| **[ItyFuzz](https://github.com/fuzzland/ityfuzz)** | MIT | EVM + MoveVM + Solana SBF | Hybrid concrete+symbolic |
| **Foundry invariant** | MIT | EVM | Built-in для базового AI-инвариант флоу |
| **[Trident](https://github.com/Ackee-Blockchain/trident)** | Apache 2.0 | Solana | Primary Solana fuzzer |
| **[Echidna](https://github.com/crytic/echidna)** | AGPL-3 | EVM | Deprecated в пользу Medusa, не использовать |

### 5.8. Formal verification

| Tool | Лицензия | Платформа | Использование |
|---|---|---|---|
| **[Certora Prover](https://github.com/Certora/CertoraProver)** | GPL-3 (open-sourced Feb 2025) | EVM + Solana + Stellar | Premium-tier deep verification |
| **[Halmos](https://github.com/a16z/halmos)** | AGPL-3 | EVM | Optional symbolic exec в Foundry |

### 5.9. Sandbox / execution environment

- **Foundry/Anvil fork-mode** для EVM (mainnet snapshot + impersonation + flash-loan integration)
- **Solana test-validator** для Solana
- **Anvil chains:** Ethereum + Base + Arbitrum + BSC форки
- **Tenderly virtual nets** — опционально для тяжёлых cases (free tier ограничен)
- **Phalcon Explorer** (BlockSec) — для post-факто call-trace анализа

---

## 6. Блокчейн-приоритеты

| Сеть | Приоритет | MVP-неделя | Обоснование |
|---|---|---|---|
| Ethereum L1 | P0 | W1 | Самый объём контрактов, эталонная EVM |
| Base | P0 | W1 | Главная ниша vibe-кодеров + 5M daily deployments |
| BSC | P1 | W3-4 | Доминант по rugpulls, ICP-территория |
| Arbitrum | P1 | W3-4 | L2 объём, EVM-совместимость |
| Solana | P2 | W7-8 | Moat (никто из конкурентов не покрывает open-source) |
| TON | Roadmap (Q4 2026) | — | Для distribution через Mini App; FunC экосистема ещё молодая |
| Polygon | Roadmap | — | Объём упал в 2025-2026 |
| Sonic SVM / MagicBlock / Eclipse | Roadmap (Y2) | — | После Solana |

---

## 7. UX

### 7.1. Web (Next.js) — основной продукт

**Главная страница (unauthenticated):**
- Hero: «Audit your smart contract in 90 seconds. From AI. For vibe-coders.»
- Big input box: contract address or paste source
- Live demo: «See score for `0x...USDC` →» (mock-результат для конкретных well-known контрактов)
- Public leaderboard ссылка («wr3 found 12 zero-days last month»)
- Pricing block с tier-таблицей

**Dashboard (authenticated):**
- Список audits с фильтрами
- Каждый audit:
  - Header: score 0-100, светофор, дата, сеть, версия движка
  - Tabs: Findings / Foundry PoCs / Invariants / Score breakdown / Raw outputs (Aderyn/Wake/Medusa)
  - Каждая finding: severity, описание, location, PoC ссылка (premium only), suggested fix
- Settings → API keys (для programmatic), webhook (Slack/Discord/Telegram), Safe Harbor onboarding helper

**Public project page (`/p/<address>`):**
- Score + светофор + tier
- Список public findings (low-severity, после disclosure okna)
- Safe Harbor badge (✅/❌)
- Метрики ончейн (TVL, age, deployer history)
- «Subscribe to alerts» CTA → авторизация

### 7.2. Telegram Mini App — top-of-funnel + lightweight

Mini App — **НЕ полная замена web**, а воронка:

- **Inline-команды бота:** `/scan 0x...` → preliminary score за 60s
- **Mini App открывает full-screen UI** с тем же scan-flow, но мобильно-оптимизированным
- **Notifications:** push-алерт для отслеживаемых контрактов («Your contract X has new high finding»)
- **Browse mode:** список топ-проектов с скорами, можно фильтровать
- **Payment:** через **TON Connect** (~0% fees после октября 2025), не через Stars (32% fee = ноу-гоу)

Full audit flow (с детальными PoC, custom настройки, billing settings) — **на web**, не в Mini App. Mini App линкует пользователя на web с auto-login через TG initData hash.

### 7.3. CLI (Y2 roadmap)

`wr3 audit ./contract.sol --network base --output report.md` — для CI/CD интеграций. После v1.0. Не в MVP.

### 7.4. Аутентификация

| Метод | Где | Зачем |
|---|---|---|
| SIWE (Sign-In With Ethereum) | Web | Натив для EVM-разработчиков |
| TON Connect | Mini App + Web | Для TG-пользователей |
| Email + password (magic link) | Web fallback | Для non-crypto-savvy |
| GitHub OAuth | Web | Для разработчиков (бонус: link to their GitHub repos) |

---

## 8. Scoring system

### 8.1. Оси (5 шт., прозрачные веса)

| Ось | Вес MVP | Описание |
|---|---|---|
| Code Security | 35% | Findings от Aderyn/Wake/Medusa/Slither + LLM-triage severity |
| Tokenomics / Centralization | 20% | owner privileges, mint authority, upgradeability, multisig threshold |
| Liquidity Risk | 15% | LP locked %, top-holder concentration, deployer-wallet activity |
| Team / KYC | 15% | Verified on Etherscan? Public team? KYC-badge? Connected to known rugpulls? |
| On-chain Behavior | 15% | TVL trend, swap volume, anomaly score, age |

Веса публикуются в README и на странице «Methodology» — анти-CertiK-black-box.

### 8.2. Шкала

- **0-39** красный (high risk) — есть critical/high findings или центральные red flags
- **40-69** жёлтый (caution) — medium issues, требует human review
- **70-89** зелёный (acceptable) — minor/info, мониторинг рекомендован
- **90-100** синий (excellent) — clean, активный bounty, Safe Harbor signed

### 8.3. Триггеры пересчёта

- Новый деплой / upgrade proxy (EIP-1967 monitor)
- Ownership transfer
- Большой transfer от deployer-адреса
- Источник верификации удалён с эксплорера (классический rug-prep)
- Новость о взломе аналога (через news pipeline)
- Истечение 30 дней
- Manual trigger от пользователя (premium)

### 8.4. Human-in-loop

- **Free tier:** AI-only с пометкой «unverified, AI-only». Защита от defamation.
- **Paid tier:** human reviewer (security researcher из команды) делает final pass перед публикацией public-findings.
- **Премиум:** human-led + AI-augmented, эссенциально competitor для Trail of Bits на 5x дешевле.

---

## 9. News & on-chain monitoring

### 9.1. News scraper

| Источник | Формат | Использование |
|---|---|---|
| Rekt News | RSS / scraping | Top-of-funnel хаков |
| SlowMist | X/Twitter via RSSHub | Real-time alerts |
| PeckShield | X/Twitter | Real-time |
| CertiK Alert | X/Twitter | Real-time (бесплатный конкурентный сигнал) |
| BlockSec Phalcon | X/Twitter | Real-time |
| [DeFiLlama Hacks API](https://api.llama.fi/) | Structured JSON | Authoritative hack list |
| [Chainalysis Crypto Crime](https://www.chainalysis.com/) | Web | Macro trends |
| Helius Blog (Solana) | RSS | Solana-specific |
| 0xngmi/blockchains | GitHub repo | DefiLlama-связанный |
| Hats Finance disclosures | Public after payout | Vulnerability examples |

**Dedup:** через Gemini text-embedding (free tier 100 RPM, 1500 RPD достаточно). Cosine similarity threshold 0.85.

**Workflow:** scraper → LLM-classifier (категория, severity, blockchain) → dedup → push в Postgres + R2-объекты → alert через bot для подписчиков.

### 9.2. On-chain monitoring (paid-tier)

| Подсистема | Стек |
|---|---|
| Mempool watching | WebSocket к Alchemy/QuickNode для pending tx (без bloXroute в MVP) |
| Forta v2 detection bots | Деплой 3-5 ботов из [forta-network/starter-kits](https://github.com/forta-network/starter-kits) (phishing, exploit, MEV-attack, large-transfer) — bonus revenue, не основной |
| OpenZeppelin Monitor (open-source) | Self-hosted на Oracle VM. Defender SaaS sunset 1 июля 2026 |
| Tenderly alerts | Free tier для simulation |
| Custom anomaly detectors | wr3 own, на базе паттернов из Solodit |

**Уведомления:** Telegram (premium), Email (free), Slack/Discord webhook (team-tier), SMS (pro-tier через Twilio pay-as-you-go).

---

## 10. OpSec — безопасность самой wr3

### 10.1. Принципы

1. **Encrypted at-rest для всех findings** — AES-256, ключи в Doppler.
2. **Multisig 2-of-3 на production access** — 3 hardware keys (YubiKey 5C) у троих участников. Один уезжает в Дубай — он всегда онлайн как primary; двое других — backup.
3. **Никаких raw findings в публичные LLM-API без ZDR.** OpenRouter ZDR / локальный Qwen3 / Bedrock с zero-retention.
4. **Все on-chain транзакции через приватные каналы:**
   - Ethereum L1: [Flashbots Protect](https://docs.flashbots.net/flashbots-protect/overview)
   - Base / Arbitrum: их sequencer private endpoints
   - BSC: BloXroute или 48 club private relay
   - Solana: [Jito](https://jito.network/) bundles
5. **Никаких .env в репозиториях.** Doppler / 1Password Secret Automation.
6. **CI/CD:** GitHub Actions с required reviews (2-of-3), branch protection, **signed commits (Sigstore/Cosign)**, запрет force-push на main, **Renovate с manual approval** (supply-chain attack vector через auto-merge).
7. **Network:** WireGuard в Oracle VM с key-rotation каждые 90 дней. Production access только с VPN. Дома — клиентский dev-доступ через bastion.
8. **Backups:** Postgres → daily snapshot в R2 (encrypted), 30-day retention.

### 10.2. Bug bounty на саму wr3

- С месяца 3 — публичная программа на Immunefi или Hats Finance
- Минимум $500 critical в начале (всё что можем потратить), apскейлится до $5k при росте revenue
- Это страховка от Hacken-сценария: «свой токен украли» = катастрофа для аудитора

### 10.3. Incident response plan

- Compromise detected → multisig вотинг → public statement в 24 часа
- Если utечка findings о клиенте → notification клиента в 2 часа + помощь с rescue/mitigation
- Если утечка ключей wr3 → immediate rotation + Doppler purge + SEAL 911 alert
- Если AI ошибочно опубликовал public claim о scam → retraction в 1 час + apology + manual review

---

## 11. План MVP по неделям (14 недель до closed beta + 6 недель до public)

### Phase 1 — Foundation (W1-W3)

**W1: Setup и архитектура**
- Repo setup, monorepo (apps/web + apps/api + packages/shared + packages/audit-engine)
- Oracle Always Free VM provisioning, Postgres + Redis установлены
- Cloudflare Workers + D1 + R2 настроены
- Next.js 15 skeleton, Tailwind, shadcn/ui
- FastAPI skeleton, Celery worker, healthchecks
- Doppler secrets, GitHub Actions CI

**W2: Ingestion + первый Aderyn-проход**
- Etherscan/BscScan/Basescan API integration
- Verified source pull, AST parsing
- Aderyn CLI integration, JSON-output парсинг
- Простой scoring stub (по числу findings)
- UI: input → result для одного контракта
- Auth: SIWE + NextAuth

**W3: Wake интеграция + LLM-триаж первого уровня**
- Wake library integration (ISC, можно линковать)
- LLM-triage agent (Claude через OpenRouter ZDR): берёт raw findings + source → отсеивает FP
- Bot logic для агентов через Claude Agent SDK
- Solodit API integration для RAG context
- Базовый report viewer

### Phase 2 — AI engine core (W4-W7)

**W4: Foundry PoC retry-loop**
- Foundry/Anvil setup, fork-mode
- Cherry-pick `core/foundry_poc_generator.py` из Aether
- PoC retry-loop: LLM generates → forge test → on revert read trace → re-generate (max 5)
- Каждый confirmed exploit → record в DB

**W5: Multi-agent triage (Trident Arena pattern)**
- 4 parallel agents: severity / FP / business-logic / cross-contract
- Cross-check / consensus layer
- Pheromone-decay blackboard (Postgres + pgvector)
- DAG-orchestrator через Claude Agent SDK

**W6: AI-fuzzing**
- Medusa integration (subprocess)
- ItyFuzz integration
- Foundry invariant generation: LLM пишет `invariant_*()` functions
- Counterexample analysis: LLM читает fuzzer-output, оценивает реальность бага

**W7: BSC + Arbitrum поддержка**
- RPC routing для multi-chain
- Bytescode handler для proxy contracts (EIP-1967 detection)
- Tested на 20 реальных контрактах из DeFiHackLabs

### Phase 3 — Scoring, UI, monetization (W8-W10)

**W8: Scoring system + reporting**
- 5-осевой scoring с публичными весами
- 0-100 + светофор
- Markdown / PDF report generation (React PDF Renderer)
- Public project pages (`/p/<address>`)

**W9: Solana support (basic)**
- Anchor IDL parser
- Sealevel-attacks dataset для RAG
- Trident fuzzer integration
- Кастомный Solana AST detector (subset of Sec3 X-Ray taxonomy)
- Tested на 10 Solana programs

**W10: Payments + Pricing**
- USDC EOA setup на Base
- Request Finance integration для invoicing
- Polar.sh / Lemon Squeezy для fiat-fallback
- Tier-based access control (Free / Hobby $29 / Team $99 / Pro $499)
- Stripe — отложить до месяца 4+ если выручка стабильна

### Phase 4 — Distribution & polish (W11-W14)

**W11: Telegram bot + Mini App**
- `@wr3_bot` с командами `/scan`, `/watch`, `/score`
- Mini App: scan-preview, browse mode, push-notifications
- TON Connect integration для payments
- initData JWT-bridge на web для auto-login

**W12: News scraper + on-chain monitoring**
- RSSHub setup для Rekt/SlowMist/PeckShield
- DeFiLlama Hacks API integration
- Gemini embedding dedup
- 3-5 Forta detection bots deployed

**W13: Internal benchmark + bug fixes**
- Запуск wr3 на 100 incidents из DefiHackLabs
- Сравнение с baseline Slither / Aderyn standalone
- Если recall <50% от GPT-5.3-Codex на EVMbench — итерация
- Bug bounty на самом wr3 (Hats Finance, $500 critical)

**W14: Closed beta soft launch**
- 10-15 invited проектов (TG-чаты «BNB Chain Builders», «Foundry», «Anchor»)
- Feedback collection через Tally form
- Iteration round
- Internal security audit нашего же кода (~$0 если самоаудит, $5k если external)

### Phase 5 — Public launch (W15-W20)

**W15-W17: Iteration based on closed beta feedback**

**W18: Marketing prep**
- Landing page final
- Blog posts: «We benchmarked wr3 vs Slither on 100 hacks» — publish results
- Demo video
- Twitter/X account, BNB Chain Discord posts

**W19: Safe Harbor integration**
- Audit-engagement template
- Safe Harbor adoption helper в UI (для проектов которые хотят опт-ин)
- SEAL 911 hotline integration

**W20: Public launch**
- Show HN, Reddit r/CryptoCurrency, r/ethereum, r/solana
- ProductHunt
- X-thread / BNB Chain Discord announce
- Press: Rekt News tip-off, Cointelegraph contact

**Месяц 7-8:** target $2-5k MRR.

---

## 12. Roadmap 6-12 мес после public launch

### Q1 после launch (мес 7-9)
- TG bot enhancements (custom alerts, watchlists)
- VS Code extension (компетитор Olympix-plugin)
- API access для programmatic clients
- Polygon support
- Public quarterly benchmark report

### Q2 (мес 10-12)
- TON-аудит поддержка (FunC)
- Certora Prover deep integration для premium tier
- White-label для крупных проектов
- Phalcon Explorer integration для post-факто forensics
- Proxy upgrade detection / monitoring (EIP-1967, transparent proxies)

### Y2 ideas
- Aptos / Sui (Move-based) поддержка
- DAO governance для findings prioritization (Sherlock-like)
- Browser extension (real-time check при подключении к dapp)
- ML-модель собственного fine-tune на DAppSCAN
- Insurance product partnership (Nexus Mutual)

---

## 13. Метрики успеха

### Closed beta (W14-W20)
- 10-15 active testers
- 5+ confirmed findings отправлено в SEAL 911
- 1 case-study с конкретным проектом («wr3 found X before deployment»)
- NPS >40

### Public launch +90 days (мес 7-8)
- **MRR $2-5k** (20-50 paying customers распределены по tier)
- **3 Forta-bots deployed** генерирующих $200-500/мес
- **2 public-leaderboard публикации** на DeFiHackLabs
- **1 publication-уровня case-study** (попадание в Rekt-news / Solodit / Cointelegraph)
- **100+ Telegram followers** в @wr3_news
- **Recall >50% от GPT-5.3-Codex** на EVMbench
- **Recall >70% на Sealevel-attacks subset** (matching Trident Arena)

### Year 1
- **MRR $10-30k**
- **1 enterprise client** ($500+/мес Pro tier)
- **DIFC Innovation License** оформлена (если revenue ≥ $5k/мес)
- **5+ Safe Harbor проектов** работают с wr3 на post-audit basis
- **Public benchmark wr3 — индустриальный reference**

---

## 14. Риск-регистр

| # | Риск | Вероятность | Воздействие | Mitigation |
|---|---|---|---|---|
| R1 | Уголовное преследование за «несанкционированную атаку» | Низкая если следуем процессу, Высокая если нарушим | Catastrophic | Жёсткое правило: активные действия только для Safe Harbor подписантов. Без юр.лица — passive disclosure через SEAL 911 |
| R2 | Defamation иск от ошибочного false-positive «scam» | Средняя | High | Human-in-loop для всех public claims, disclaimer в TOS, manual review до публикации |
| R3 | Утечка 0-day findings о клиенте | Низкая если OpSec соблюдён | Catastrophic для клиента + civil/criminal liability для нас | Encrypted at-rest, multisig доступ, OpenRouter ZDR, локальный Qwen для самых чувствительных |
| R4 | Низкий revenue первые 3-6 мес | Высокая | Medium (выживаемо) | Audit-контесты на Hats/CodeHawks как bridge revenue в мес 1-3, $200-1500 CAPEX а не $15k+ |
| R5 | Конкурент (Cluster Protocol / Matterhorn / Olympix) заливает нишу | Высокая | Medium | Speed-to-market — закрыть нишу до Q3 2026. Moat: Solana + TG + transparency + benchmark |
| R6 | NavyAI / OpenRouter ban или закрытие | Средняя | Medium | Multi-provider routing, локальный Qwen3-Coder как fallback |
| R7 | Anthropic / OpenAI banaют аккаунт за security-prompts | Низкая через ZDR-провайдер | Medium | Все sensitive промпты через OpenRouter ZDR или локально |
| R8 | Key-person risk: security researcher уходит | Средняя | High | Internal playbooks с месяца 1, документация процессов, knowledge не в голове |
| R9 | Solana ecosystem schism / Anchor breaking change | Низкая | Medium | Tracking Anchor releases, Trident actively maintained Ackee |
| R10 | Regulatory changes (US, UAE, EU) | Низкая | Medium-High | Бизнес гибкий (NM LLC легко мигрировать в DIFC если надо), нет heavy infrastructure investment |
| R11 | AI-аудит становится commodity к концу 2026 | Высокая | High | Moat не в технологии (повторят), а в SEAL+TG-distribution+benchmark-репутации |
| R12 | Oracle Cloud Always Free reclaim инстанса | Средняя | Low | Multi-region backup, Hetzner $4/мес migration plan готов |
| R13 | Hacken-сценарий: компрометация самого wr3 | Низкая через multisig | Existential | Bug bounty с дня 1 на саму wr3, external audit нашего кода перед public launch |

---

## 15. Бюджет

### CAPEX (one-time)

| Item | Cost | Notes |
|---|---|---|
| New Mexico LLC (отложить до месяца 4) | $50 + $35-100 registered agent | Опционально для bootstrap |
| Domain (1 year) | $10 | Cloudflare Registrar |
| Hardware keys (3× YubiKey 5C) | $180 | Multisig access |
| Initial Hats/Code4rena bounty deposit на саму wr3 | $500 | Месяц 3 |
| External security audit нашего кода (Y2) | $0 → $5-15k | Опционально, после public launch |
| **Минимум CAPEX MVP** | **~$200** | До public launch |
| **Реалистичный CAPEX Y1** | **$1000-1500** | Включая audit + LLC + bounty |

### OPEX (monthly)

| Item | Cost | Notes |
|---|---|---|
| Cloudflare Workers + D1 + R2 | $0 | Free tier |
| Oracle Always Free VM | $0 | Forever |
| Postgres self-hosted на Oracle | $0 | — |
| GPU для self-hosted LLM (RTX 4090 у друга) | $0 | Или vast.ai pay-per-use $0.30-1/час |
| LLM API через OpenRouter + NavyAI | $0-100 | Scales with usage, free tiers покрывают MVP |
| RPC (Alchemy free + drpc fallback) | $0 | Free tier |
| Sentry / UptimeRobot / Telegram bot alerts | $0 | Free tiers |
| Doppler secrets | $0 | Free 10 secrets |
| GitHub Actions (public repo) | $0 | Unlimited |
| Email (Resend free 100/день) | $0 | — |
| **Итого OPEX MVP** | **$0-100/мес** | До 1000+ audits/день |

### Bridge revenue (мес 1-3)

- Audit-контесты Hats Finance / CodeHawks / Cantina: $500-3k/мес irregular
- Это finanstrue bootstrap до paid subscriptions начнут поступать в мес 3+

### Total cash needed

- **Месяц 1-3 (до первого paying customer):** ~$200 CAPEX + $0-100/мес OPEX × 3 = **$200-500**
- **Месяц 4-6 (до $1k MRR):** + LLC $150 + bounty $500 = **~$900 total**
- **Месяц 7-12 (до $5-10k MRR):** marketing + external audit опц. = **$2-5k total**

Полный bootstrap до выживаемого revenue — **под $1000 personal investment**. Plus opportunity grants:
- Optimism RetroPGF Round 6+ (security category): $20-100k через 6-12 мес
- Arbitrum DAO security subcommittee: $10-50k
- Solana Foundation grants: $10-50k под Solana-аудит
- EF Academic Grants: если novel research

---

## 16. Команда и роли

### 16.1. 3 человека + AI

| Роль | Обязанности | Стек |
|---|---|---|
| **Tech Lead** | Архитектура, DevSecOps, full-stack, блокчейн-интеграции | Next.js, FastAPI, viem, Foundry, Postgres |
| **Security Researcher** | Solidity/Rust audit knowledge, AI-fuzzing инварианты, DeFi attack vectors | Solidity, Anchor, Slither/Aderyn/Wake, Halmos, Certora |
| **Product/Growth** | Community (TG/Discord/X), sales, content, customer success | Telegram bot, X, content writing |

### 16.2. AI-агенты как force multiplier

- Каждый человек × Claude Opus 4.7 = ~80% качества senior с большим bandwidth
- Claude Agent SDK для оркестрации (audit-engine агенты + dev-агенты)
- Cursor / Claude Code как dev environment

### 16.3. Что НЕ нанимать

- ❌ Full-time security researcher senior ($250-450k/год) — заменяется Mid + Claude Opus
- ❌ DevOps — Oracle Always Free + Cloudflare Workers не требуют ops
- ❌ Designer — shadcn/ui + Tailwind покрывают
- ❌ Lawyer фuller-time — engagement letter templates от SEAL + ChatGPT-помощь

### 16.4. Что покупать external

- Legal review engagement letter / TOS (один раз, $1-3k через online-lawyers like LegalNature)
- External security audit нашего кода перед public launch ($5-15k или free от сообщества Hats)

---

## 17. Что НЕ делаем (явно)

Чёткий out-of-scope для MVP — защита от scope creep:

1. ❌ Mempool monitoring (premium feature, roadmap Y2)
2. ❌ TON / Aptos / Sui / Cardano audit support (roadmap)
3. ❌ Browser extension (roadmap)
4. ❌ DAO governance для findings (roadmap)
5. ❌ White-label (roadmap)
6. ❌ Custom inavriant DSL (используем Foundry/Medusa stock)
7. ❌ ML-fine-tune собственной модели (используем готовые)
8. ❌ Audit-as-service для enterprise top-100 (другая лига, не лезем)
9. ❌ Cyber insurance product (роль страховщика, не наша)
10. ❌ Token / fundraising (не нужно для bootstrap)

---

## 18. Open questions для уточнения с командой

После основания команды и первой недели работы:

- Confirmation персонального LLM-провайдера каждого участника (api.navy vs Claude direct vs другой)
- Конкретный GPU: чей RTX 4090, или платим vast.ai
- Резидентство участников (важно для tax-implications NM LLC payouts)
- Кто из троих держит primary multisig signer (тот, кто в самой стабильной юрисдикции)
- График — full-time vs part-time, sprint-cadence

---

## 19. References (полный список источников ресёрча)

### Конкуренты
- [CertiK Skynet methodology](https://skynet.certik.com/skynet-score-methodology)
- [Merlin DEX rugpull (Coindesk)](https://www.coindesk.com/tech/2023/04/27/dex-merlin-and-certik-plan-to-compensate-2m-to-users-impacted-in-rugpull)
- [Hacken HAI bridge compromise (Rekt)](https://rekt.news/hacken-rekt)
- [Olympix Balancer V2 post-mortem](https://olympix.security/blog/balancer-lost-121m-because-the-industry-still-doesnt-understand-defi-security)
- [Olympix vs Slither EigenLayer (self-published)](https://olympix.security/blog/comparing-olympix-and-slither-on-the-eigen-layer-code-base)
- [Cantina Crunchbase Series A](https://www.crunchbase.com/organization/cantina-79dc)
- [Sherlock AI V2 launch Feb 2026](https://sherlock.xyz/post/introducing-sherlock-ai-v2)
- [Sec3 X-Ray GitHub](https://github.com/sec3-product/x-ray)
- [Cluster Protocol CodeXero $5M raise](https://www.theblock.co/post/398581/cluster-protocol-raises-5-million-to-accelerate-codexero-a-browser-native-vibe-coding-ai-ide-for-evm-bringing-total-funding-to-7-75-million)
- [Matterhorn ASI vibe-coding security](https://www.coca.xyz/post/enhanced-tools-introduced-to-secure-ai-vibe-coding-in-cryptocurrency)
- [ChainGPT AI Smart Contract Auditor](https://docs.chaingpt.org/ai-tools-and-applications/ai-smart-contract-auditor)

### AI-аудит репозитории
- [l33tdawg/aether](https://github.com/l33tdawg/aether) — cherry-pick
- [Cyfrin/aderyn](https://github.com/Cyfrin/aderyn) — primary static EVM
- [Ackee-Blockchain/wake](https://github.com/Ackee-Blockchain/wake) — secondary static (ISC permissive)
- [crytic/slither](https://github.com/crytic/slither) — fallback на legacy
- [crytic/medusa](https://github.com/crytic/medusa) — primary fuzzer EVM
- [fuzzland/ityfuzz](https://github.com/fuzzland/ityfuzz) — hybrid fuzzer
- [Ackee-Blockchain/trident](https://github.com/Ackee-Blockchain/trident) — primary Solana fuzzer
- [Certora/CertoraProver](https://github.com/Certora/CertoraProver) — formal verification (open-sourced Feb 2025)
- [a16z/halmos](https://github.com/a16z/halmos) — optional symbolic exec
- [trailofbits/slither-mcp](https://github.com/trailofbits/slither-mcp) — MCP architecture reference
- [Ackee-Blockchain Trident Arena blog](https://ackee.xyz/blog/trident-arena-multi-agent-ai-security-for-solana-programs/) — benchmark target
- [advaitbd/smartguard](https://github.com/advaitbd/smartguard) — Skeptic-agent pattern reference
- [koala73/worldmonitor](https://github.com/koala73/worldmonitor) — news pipeline pattern (AGPL — паттерн, не код)
- [Armur-Ai/Pentest-Swarm-AI](https://github.com/Armur-Ai/Pentest-Swarm-AI) — blackboard with pheromone-decay pattern
- [PurpleAILAB/Decepticon](https://github.com/PurpleAILAB/Decepticon) — multi-agent reference
- [GreyDGL/PentestGPT](https://github.com/GreyDGL/PentestGPT) — agentic pipeline reference

### Knowledge sources
- [Solodit API (Cyfrin)](https://solodit.cyfrin.io/) — primary RAG
- [SunWeb3Sec/DeFiHackLabs](https://github.com/SunWeb3Sec/DeFiHackLabs) — 689 PoC incidents
- [coral-xyz/sealevel-attacks](https://github.com/coral-xyz/sealevel-attacks) — Solana golden dataset
- [InPlusLab/DAppSCAN](https://github.com/InPlusLab/DAppSCAN) — large corpus
- [smartbugs/smartbugs-curated](https://github.com/smartbugs/smartbugs-curated) — benchmark suite
- [SWC Registry](https://swcregistry.io/) — taxonomy
- [Helius Solana hacks blog](https://www.helius.dev/blog/solana-hacks)

### Безопасность и юридика
- [SEAL Whitehat Safe Harbor Framework](https://frameworks.securityalliance.org/safe-harbor/whitehat/)
- [SEAL Safe Harbor GitHub registry](https://github.com/security-alliance/safe-harbor)
- [SEAL 911 hotline](https://securityalliance.org/our-work/seal-911)
- [SEAL Legal Defense Fund](https://www.bitsofblocks.io/post/seal-launches-legal-defence-fund-for-whitehats)
- [Immunefi Safe Harbor](https://immunefi.com/safe-harbor/)
- [Anthropic Cyber Verification Program](https://undercodetesting.com/anthropics-cyber-verification-program-unlocking-for-offensive-security-heres-how-to-apply-and-use-it-video/)
- [UAE Federal Decree-Law 34/2021](https://uaelegislation.gov.ae/en/legislations/1526/download)
- [Mango Markets Eisenberg overturned (TRM Labs)](https://www.trmlabs.com/resources/blog/breaking-federal-judge-overturns-all-criminal-convictions-in-mango-markets-case-against-avraham-eisenberg)

### Инфраструктура и LLM
- [OpenRouter ZDR](https://openrouter.ai/docs/guides/features/zdr)
- [OpenRouter Privacy](https://openrouter.ai/privacy)
- [The Register — Anthropic ban third-party proxies](https://www.theregister.com/2026/02/20/anthropic_clarifies_ban_third_party_claude_access/)
- [Qwen3-Coder 30B-A3B specs](https://apxml.com/models/qwen3-30b-a3b)
- [Cloudflare Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/)
- [Oracle Always Free guide](https://medium.com/@imvinojanv/setup-always-free-vps-with-4-ocpu-24gb-ram-and-200gb-storage-the-ultimate-oracle-cloud-guide-bed5cbf73d34)
- [Wyoming vs New Mexico LLC 2026](https://usllcglobal.com/guides/wyoming-vs-delaware)
- [Cheapest MoR 2026](https://dodopayments.com/blogs/cheapest-merchant-of-record)
- [Flashbots Protect](https://docs.flashbots.net/flashbots-protect/overview)
- [Jito bundles (Solana)](https://jito.network/)

### Бенчмарки и evaluation
- [EVMbench (OpenAI/Paradigm)](https://openai.com/index/introducing-evmbench/) — главный benchmark
- [ACToolBench paper ASE'25](https://daoyuan14.github.io/papers/ASE25_ACToolBench.pdf)
- [SmartLLM arXiv 2502.13167](https://arxiv.org/abs/2502.13167)
- [FTSmartAudit arXiv 2410.13918](https://arxiv.org/abs/2410.13918)

### Рынок крипто-аудита
- [Immunefi $100M payouts milestone (TheBlock)](https://www.theblock.co/post/301025/web3-immunefi-ethical-hacker-payouts)
- [Immunefi 2024→2025 critical payout drop -45%](https://x.com/jack__sanford/status/1998729408857735202)
- [Smart Contract Bug Bounty Statistics 2026](https://sqmagazine.co.uk/smart-contract-bug-bounties-statistics/)
- [Sherlock smart contract audit pricing 2026](https://sherlock.xyz/post/smart-contract-audit-pricing-a-market-reference-for-2026)
- [Zealynx — what audits actually cost 2026](https://www.zealynx.io/blogs/what-smart-contract-audits-actually-cost)
- [Poly Network Mr. Whitehat](https://fintechmagazine.com/crypto/timeline-poly-network-and-curious-case-mr-whitehat)
- [Euler $200M recovery negotiation (Fortune)](https://fortune.com/crypto/2023/04/06/how-an-elite-team-pressured-a-hacker-to-return-200m-he-stole-from-defi-platorm-euler/)

### Distribution
- [BNB Chain Discord](https://discord.com/invite/bnbchain)
- [BNB Chain Telegram community](https://t.me/BNBchaincommunity)
- [Telegram Stars fees guide 2026](https://grambase.ai/blog/telegram-stars-guide-2026)
- [TON Network fees post-Telegram governance](https://www.ainvest.com/news/ton-network-fees-drop-telegram-takes-governance-2605/)
- [FEMITBOT Telegram Mini App fraud network May 2026](https://hackread.com/femitbot-telegram-mini-apps-crypto-scam-android-malware/)
- [Farcaster MAU decline](https://blockeden.xyz/blog/2025/10/28/farcaster-in-2025-the-protocol-paradox/)

---

## 20. Финальный sanity-check

**Три постулата, без которых проект не получится:**

1. **Хирургическая ниша.** Мелкие проекты на BSC / Base / Solana с бюджетом $200-2000. Не лезть в enterprise top-100 — там CertiK / ToB / Cantina, у нас нет шансов.
2. **Cherry-pick OSS, не велосипед.** Aether seed data + Aderyn + Wake + Medusa + Trident + Certora + ItyFuzz + Solodit RAG = ~70% работы готовой бесплатно. Наш value — оркестрация + scoring + distribution + benchmark.
3. **Distribution через TG + transparency.** CertiK туда не идёт. Их Skynet — black-box. Мы публикуем веса, открываем benchmark на DefiHackLabs, идём в BNB Chain Discord. Это и есть moat.

**Без чего проект не выживет:**
- Soft launch не позже Q3 2026 — окно закрывается, заходят 5-10 финансированных конкурентов.
- Качество ≥50% от GPT-5.3-Codex baseline на EVMbench до public — иначе trust не возникнет.
- Zero-tolerance к «активным действиям без Safe Harbor opt-in» — один эпизод = уголовка + конец проекта.

**На что готовы пойти:**
- Бесплатные ресурсы до последнего, юр.лицо отложить до месяца 4
- Team-tier OPS на 3 человек с компенсацией хардвера multisig + GPU
- Иметь revenue-bridge через audit-контесты в первые 3 месяца

---

**Документ закрыт. Версия 1.0. К пересмотру через 60 дней после старта работы или при изменении 2+ из перечисленных предпосылок.**
