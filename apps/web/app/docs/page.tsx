import Link from "next/link";
import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — документация" };

const PRIMARY = "#4ade80";
const MUTED = "#8bb88b";
const DIM = "#547654";
const FG = "#a8e6a8";
const HI = "#d4ffd4";

const codeBlock: React.CSSProperties = {
  background: "#0a0e0a",
  padding: 12,
  border: `1px solid ${DIM}`,
  borderRadius: 4,
  fontSize: 11,
  color: FG,
  overflowX: "auto",
  fontFamily: "inherit",
  marginTop: 8,
};

const h2: React.CSSProperties = {
  color: HI,
  fontSize: 20,
  marginTop: 40,
  marginBottom: 12,
  fontWeight: 700,
  letterSpacing: "-0.01em",
};

const h3: React.CSSProperties = {
  color: HI,
  fontSize: 15,
  marginTop: 24,
  marginBottom: 8,
  fontWeight: 700,
};

const tableBase: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 12,
  marginTop: 8,
};

const td: React.CSSProperties = {
  padding: "6px 10px",
  borderBottom: `1px solid ${DIM}`,
  verticalAlign: "top",
};

export default function DocsPage() {
  return (
    <TerminalPageShell title="Документация" eyebrow="// docs">
      <nav
        style={{
          color: MUTED,
          fontSize: 13,
          marginBottom: 24,
          padding: "12px 16px",
          background: "#0a0e0a",
          border: `1px solid ${DIM}`,
          borderRadius: 6,
          lineHeight: 1.8,
        }}
      >
        Содержание:{" "}
        <Toc href="#quickstart">Быстрый старт</Toc> ·{" "}
        <Toc href="#pipeline">Пайплайн</Toc> ·{" "}
        <Toc href="#scoring">Оценка</Toc> ·{" "}
        <Toc href="#owner">Настройки пайплайна</Toc> ·{" "}
        <Toc href="#api">API</Toc> ·{" "}
        <Toc href="#faq">FAQ</Toc>
      </nav>

      <h2 id="quickstart" style={h2}>Быстрый старт</h2>
      <p>Самый короткий путь до рабочего аудита:</p>
      <ol style={{ paddingLeft: 24, color: FG, lineHeight: 1.8 }}>
        <li>
          Откройте{" "}
          <a href="https://t.me/KitronBot" style={{ color: PRIMARY, textDecoration: "underline" }}>
            @KitronBot
          </a>{" "}
          в Telegram.
        </li>
        <li>
          Нажмите <code>Start</code>, затем меню <code>wr3 audit</code>.
        </li>
        <li>Введите адрес контракта (0x… для EVM, base58 для Solana).</li>
        <li>
          Выберите сеть, нажмите <code>Запустить аудит</code>.
        </li>
        <li>Пайплайн отработает за 30–60 секунд — получите оценку и список находок.</li>
      </ol>
      <aside
        style={{
          color: MUTED,
          fontSize: 13,
          marginTop: 16,
          padding: "10px 14px",
          background: "#0a0e0a",
          border: `1px solid ${DIM}`,
          borderRadius: 4,
        }}
      >
        Пример для проверки: USDC —{" "}
        <code>0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48</code> в сети ethereum.
      </aside>

      <h2 id="pipeline" style={h2}>Пайплайн — 7 стадий</h2>
      <p>
        Каждый скан идёт через один и тот же DAG. Стадии можно отключать
        per-user через <Link href="#owner" style={{ color: PRIMARY }}>настройки владельца</Link>.
      </p>
      <pre style={codeBlock}>
{`стадия 1   ingestion        Etherscan V2 → подтянуть verified source
                            резолв прокси (EIP-1967 implementation)
стадия 2   static-analysis   baseline regex + Aderyn + Wake + Slither (EVM)
                            Sealevel-attacks (Solana)
стадия 3   ai-triage         4 параллельных Claude-агента → консенсус
                              · severity-classifier
                              · false-positive-filter
                              · business-logic-reasoner
                              · cross-contract-analyzer
стадия 4   poc-generation    LLM пишет Foundry-тест для HIGH/CRITICAL
                            → forge test --json → retry-loop при фейле
                            (максимум 3 попытки на находку)
стадия 5   ai-fuzzing        LLM генерит invariant_* функции
                            → medusa fuzz / forge invariant testing
                            → counter-example analyzer: реальный баг vs артефакт
стадия 6   scoring           5 осей, 0–100, светофор-вердикт
                             (formal verification — Y2 roadmap, не в MVP)`}
      </pre>

      <h3 style={h3}>стоимость по стадиям</h3>
      <div style={{ overflowX: "auto" }}>
        <table style={tableBase}>
          <thead>
            <tr style={{ color: MUTED, fontSize: 10 }}>
              <th style={{ ...td, textAlign: "left" }}>СТАДИЯ</th>
              <th style={{ ...td, textAlign: "left" }}>LLM-ВЫЗОВЫ</th>
              <th style={{ ...td, textAlign: "left" }}>БИНАРЬ</th>
              <th style={{ ...td, textAlign: "left" }}>ВРЕМЯ</th>
            </tr>
          </thead>
          <tbody style={{ color: FG }}>
            <tr><td style={td}>ingestion</td><td style={td}>0</td><td style={td}>—</td><td style={td}>&lt;1с</td></tr>
            <tr><td style={td}>static</td><td style={td}>0</td><td style={td}>aderyn/wake/slither</td><td style={td}>3–15с</td></tr>
            <tr><td style={td}>triage</td><td style={td}>4 параллельно</td><td style={td}>—</td><td style={td}>5–20с</td></tr>
            <tr><td style={td}>poc</td><td style={td}>1–3 / находку</td><td style={td}>forge</td><td style={td}>10–60с</td></tr>
            <tr><td style={td}>fuzzing</td><td style={td}>1 (gen) + 1 (analyze)</td><td style={td}>medusa / forge</td><td style={td}>15–120с</td></tr>
            <tr><td style={td}>scoring</td><td style={td}>0</td><td style={td}>—</td><td style={td}>&lt;100мс</td></tr>
          </tbody>
        </table>
      </div>

      <h2 id="scoring" style={h2}>Оценка — 5 осей</h2>
      <p>
        Финальный score 0–100 — взвешенное среднее по 5 осям с{" "}
        <b style={{ color: HI }}>публичными весами</b>. Все 5 осей активны
        и получают реальные сигналы от независимых источников. Каждая ось
        активируется только при наличии данных — если enricher не ответил,
        вес перераспределяется по оставшимся осям честно.
      </p>
      <div style={{ overflowX: "auto" }}>
        <table style={tableBase}>
          <thead>
            <tr style={{ color: MUTED, fontSize: 11 }}>
              <th style={{ ...td, textAlign: "left" }}>Ось</th>
              <th style={{ ...td, textAlign: "right" }}>Вес</th>
              <th style={{ ...td, textAlign: "left" }}>Сигнал</th>
            </tr>
          </thead>
          <tbody style={{ color: FG }}>
            <tr><td style={td}>Code Security</td><td style={{ ...td, textAlign: "right" }}>35%</td><td style={td}>Aderyn + Wake + Slither + baseline regex → штраф по severity</td></tr>
            <tr><td style={td}>Tokenomics / Centralization</td><td style={{ ...td, textAlign: "right" }}>20%</td><td style={td}>GoPlus: owner-привилегии, mint authority, proxy, honeypot</td></tr>
            <tr><td style={td}>Liquidity Risk</td><td style={{ ...td, textAlign: "right" }}>15%</td><td style={td}>GoPlus: holder count, creator %, sell tax, exit barriers</td></tr>
            <tr><td style={td}>Team / KYC</td><td style={{ ...td, textAlign: "right" }}>15%</td><td style={td}>MetaMask phishing list + deployer nonce + source verification</td></tr>
            <tr><td style={td}>On-chain Behavior</td><td style={{ ...td, textAlign: "right" }}>15%</td><td style={td}>Etherscan: возраст контракта (дата деплоя vs. rug-статистика)</td></tr>
          </tbody>
        </table>
      </div>

      <h3 style={h3}>Severity → штраф к оценке</h3>
      <pre style={codeBlock}>
{`critical    -40   любая critical-находка форсит tier=red
high        -20   потолок tier = yellow
medium       -7
low          -2
info          0`}
      </pre>

      <h3 style={h3}>Tier mapping</h3>
      <pre style={codeBlock}>
{`0  ≤ score < 40    red       Высокий риск     critical/high или много medium
40 ≤ score < 70    yellow    Осторожно        medium-severity находки
70 ≤ score < 90    green     Приемлемо        только минорные замечания
90 ≤ score ≤ 100   blue      Отлично          значимых находок нет`}
      </pre>

      <h2 id="owner" style={h2}>Настройки пайплайна</h2>
      <p>
        Откройте Mini App и нажмите <code>Настройки</code> в шапке. Каждый
        переключатель реально меняет поведение пайплайна при следующем скане:
      </p>
      <div style={{ overflowX: "auto" }}>
        <table style={tableBase}>
          <thead>
            <tr style={{ color: MUTED, fontSize: 11 }}>
              <th style={{ ...td, textAlign: "left" }}>Параметр</th>
              <th style={{ ...td, textAlign: "left" }}>Эффект</th>
            </tr>
          </thead>
          <tbody style={{ color: FG }}>
            <tr><td style={td}><code>auto_poc</code></td><td style={td}>Foundry PoC retry-loop для HIGH/CRITICAL находок. По умолчанию: включено.</td></tr>
            <tr><td style={td}><code>auto_fuzzing</code></td><td style={td}>AI-fuzzing через forge invariant testing. По умолчанию: включено.</td></tr>
            <tr><td style={td}><code>multi_agent_triage</code></td><td style={td}>4 параллельных Claude-агента вместо одного. По умолчанию: включено.</td></tr>
            <tr><td style={td}><code>continuous_monitoring</code></td><td style={td}>Каждые 6 ч проверяем ваши контракты через Etherscan — алерт при смене source / владельца / impl. Без LLM-расхода.</td></tr>
            <tr><td style={td}><code>anonymous_in_public</code></td><td style={td}>Скрыть себя из публичного лидерборда. По умолчанию: выключено.</td></tr>
          </tbody>
        </table>
      </div>

      <h2 id="api" style={h2}>API</h2>
      <p>Публичные эндпоинты (без авторизации):</p>
      <pre style={codeBlock}>
{`GET  /v1/public/scans?limit=50&min_score=0
GET  /v1/public/stats
GET  /v1/public/incidents?limit=30&days=120
GET  /v1/scan/{scan_id}/report.md          markdown-экспорт отчёта
GET  /v1/scan/{job_id}/progress            JSON-snapshot прогресса (polling)
GET  /v1/health
GET  /v1/version`}
      </pre>

      <p style={{ marginTop: 16 }}>С авторизацией (Bearer JWT из Telegram initData):</p>
      <pre style={codeBlock}>
{`POST   /v1/scan                      { address, network, source_code? } -> { job_id }
GET    /v1/scan/{scan_id}            полный скан + находки
GET    /v1/scan/{job_id}/events      SSE-стрим прогресса пайплайна
GET    /v1/scan/me                   последние сканы текущего пользователя
GET    /v1/auth/me                   текущий пользователь
GET    /v1/auth/preferences          настройки владельца
PATCH  /v1/auth/preferences          частичное обновление`}
      </pre>

      <h2 id="faq" style={h2}>FAQ</h2>

      <h3 style={h3}>wr3 умеет аудитить Solana?</h3>
      <p>
        Да. Собственный анализатор на базе{" "}
        <a href="https://github.com/coral-xyz/sealevel-attacks" style={{ color: PRIMARY, textDecoration: "underline" }}>
          Sealevel-attacks
        </a>{" "}
        для Anchor-программ — покрываем 11 из 13 категорий (signer auth, arbitrary
        CPI, PDA bump из caller input и др.).
      </p>

      <h3 style={h3}>Зачем оценка, а не просто список находок?</h3>
      <p>
        Одно число даёт не-эксперту принять решение go / no-go за пару секунд.
        Разбивка раскрывается в одном клике. Существующие scoring-инструменты
        (CertiK Skynet) — <b style={{ color: HI }}>pay-to-play</b> со скрытыми
        весами; wr3 веса публикует.
      </p>

      <h3 style={h3}>Можно сканировать контракт без verified-source на Etherscan?</h3>
      <p>
        Да — вставьте исходный код прямо в форму скана. Пайплайн работает
        одинаково независимо от того, пришёл source с эксплорера или от вас.
      </p>

      <h3 style={h3}>Как экспортировать находки?</h3>
      <p>
        JSON: <code>GET /v1/scan/{`{id}`}</code> с вашим токеном. Markdown (для
        GitHub-issue или клиента): <code>GET /v1/scan/{`{id}`}/report.md</code>{" "}
        — публичный, без авторизации, скачивается как файл.
      </p>

      <h3 style={h3}>Как удалить свои данные?</h3>
      <p>
        Напишите{" "}
        <a href="https://t.me/KitronBot" style={{ color: PRIMARY, textDecoration: "underline" }}>
          @KitronBot
        </a>{" "}
        слово <code>delete</code> — удалим аккаунт и все связанные сканы в
        течение 72 часов.
      </p>

      <h2 style={h2}>Ссылки</h2>
      <ul style={{ color: FG }}>
        <li><a href="https://github.com/StarDust1508/WR3" style={{ color: PRIMARY }}>GitHub-репозиторий</a></li>
        <li><a href="https://github.com/coral-xyz/sealevel-attacks" style={{ color: PRIMARY }}>Sealevel-attacks taxonomy</a></li>
        <li><a href="https://github.com/Cyfrin/aderyn" style={{ color: PRIMARY }}>Aderyn static analyzer</a></li>
        <li><a href="https://github.com/Ackee-Blockchain/wake" style={{ color: PRIMARY }}>Wake framework</a></li>
        <li><a href="https://github.com/crytic/slither" style={{ color: PRIMARY }}>Slither</a></li>
        <li><a href="https://github.com/crytic/medusa" style={{ color: PRIMARY }}>Medusa fuzzer</a></li>
        <li><a href="https://book.getfoundry.sh" style={{ color: PRIMARY }}>Foundry book</a></li>
      </ul>
    </TerminalPageShell>
  );
}

function Toc({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} style={{ color: PRIMARY, textDecoration: "none" }}>
      {children}
    </a>
  );
}
