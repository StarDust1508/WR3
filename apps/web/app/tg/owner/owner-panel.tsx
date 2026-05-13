"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  PREFS_DEFAULT,
  type Prefs,
  fetchPrefs,
  patchPrefs,
} from "@/lib/tg-prefs";

/**
 * Owner panel. Every toggle here is wired into real backend behaviour:
 *   auto_poc / auto_fuzzing / multi_agent_triage — read by scan_worker
 *     each scan; off = pipeline skips that stage and saves tokens.
 *   continuous_monitoring — read by Celery beat sweeper every 6h; on =
 *     contract is re-checked via Etherscan for source/owner/impl changes
 *     and alerts back via the bot.
 *   anonymous_in_public — read by /v1/public/scans; on = your handle
 *     and scan rows are filtered out of the leaderboard.
 */
export function OwnerPanel() {
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savingKey, setSavingKey] = useState<keyof Prefs | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const p = await fetchPrefs();
        if (!cancelled) setPrefs(p);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  async function toggle(key: keyof Prefs) {
    if (!prefs) return;
    const next = !prefs[key];
    setPrefs({ ...prefs, [key]: next });
    setSavingKey(key);
    try {
      const merged = await patchPrefs({ [key]: next });
      setPrefs(merged);
    } catch (e) {
      // rollback on error
      setPrefs(prefs);
      setError((e as Error).message);
    } finally {
      setSavingKey(null);
    }
  }

  return (
    <main className="mx-auto max-w-xl px-4 pb-32 pt-4">
      <Link
        href="/tg"
        className="text-xs"
        style={{ color: "var(--hb-text-dim)", textDecoration: "none" }}
      >
        ‹ Назад
      </Link>

      <h1
        className="mt-4 text-lg font-bold"
        style={{ color: "var(--hb-text-hi)" }}
      >
        Настройки пайплайна
      </h1>
      <p
        className="mt-1 text-[12px] leading-relaxed"
        style={{ color: "var(--hb-text-dim)" }}
      >
        Изменения применяются со следующего скана. По умолчанию все стадии включены.
      </p>

      {error && (
        <p
          className="mt-3 text-xs leading-relaxed"
          style={{
            color: "var(--hb-error)",
            background: "rgba(248,113,113,0.08)",
            border: "1px solid rgba(248,113,113,0.30)",
            padding: "8px 10px",
            borderRadius: 4,
          }}
        >
          {error}
        </p>
      )}

      {prefs === null ? (
        <p
          className="mt-8 text-center text-xs hb-dots"
          style={{ color: "var(--hb-text-dim)" }}
        >
          Загрузка
        </p>
      ) : (
        <section className="mt-5 flex flex-col gap-2">
          <Toggle
            label="Foundry PoC retry-loop"
            help="Пытается воспроизвести HIGH/CRITICAL находки реальным Foundry-тестом. Расход: 1–3 LLM-вызова на находку + forge run."
            value={prefs.auto_poc}
            saving={savingKey === "auto_poc"}
            onClick={() => toggle("auto_poc")}
          />
          <Toggle
            label="AI-fuzzing"
            help="Генерирует инварианты и прогоняет forge invariant testing. Самая дорогая стадия — отключайте на ранних драфтах."
            value={prefs.auto_fuzzing}
            saving={savingKey === "auto_fuzzing"}
            onClick={() => toggle("auto_fuzzing")}
          />
          <Toggle
            label="Multi-agent триаж"
            help="4 параллельных Claude-агента (severity / FP / business-logic / cross-contract). Off — один LLM-вызов с худшей точностью, но в 3–4 раза дешевле."
            value={prefs.multi_agent_triage}
            saving={savingKey === "multi_agent_triage"}
            onClick={() => toggle("multi_agent_triage")}
          />
          <Toggle
            label="Мониторинг контрактов"
            help="Каждые 6 часов проверяем ваши контракты через Etherscan и присылаем алерт при смене source code, владельца или impl. Без LLM-расхода."
            value={prefs.continuous_monitoring}
            saving={savingKey === "continuous_monitoring"}
            onClick={() => toggle("continuous_monitoring")}
          />
          <Toggle
            label="Анонимность в публичном"
            help="Скрывает ваш профиль и сканы из публичного лидерборда и общего индекса."
            value={prefs.anonymous_in_public}
            saving={savingKey === "anonymous_in_public"}
            onClick={() => toggle("anonymous_in_public")}
          />
        </section>
      )}

      {prefs && (
        <section className="mt-8">
          <h2 className="tg-hint mb-2">Прогноз для следующего скана</h2>
          <div
            className="tg-card text-[11px] leading-relaxed"
            style={{ color: "var(--hb-text-dim)" }}
          >
            <p>
              <span style={{ color: "var(--hb-text-hi)" }}>~{estimateCost(prefs)}</span>
              {" "}LLM-токенов на средний контракт ·{" "}
              <span style={{ color: "var(--hb-text-hi)" }}>~{estimateDuration(prefs)}с</span>
              {" "}общая длительность.
            </p>
            <p className="mt-2" style={{ color: "var(--hb-text-muted)" }}>
              Оценки приблизительны и зависят от размера контракта.
            </p>
          </div>
        </section>
      )}
    </main>
  );
}

function estimateCost(p: Prefs): string {
  let tokens = 8_000; // baseline + ingestion is roughly constant
  if (p.multi_agent_triage) tokens += 18_000;
  else tokens += 5_000;
  if (p.auto_poc) tokens += 12_000;
  if (p.auto_fuzzing) tokens += 9_000;
  if (tokens >= 1000) return `${Math.round(tokens / 1000)}K`;
  return String(tokens);
}

function estimateDuration(p: Prefs): number {
  let secs = 20; // ingestion + static
  if (p.multi_agent_triage) secs += 15;
  else secs += 6;
  if (p.auto_poc) secs += 18;
  if (p.auto_fuzzing) secs += 30;
  return Math.round(secs);
}

function Toggle({
  label,
  help,
  value,
  saving,
  onClick,
}: {
  label: string;
  help: string;
  value: boolean;
  saving: boolean;
  onClick: () => void;
}) {
  return (
    <div className="tg-card flex items-start gap-3">
      <div className="min-w-0 flex-1">
        <p
          className="text-sm font-bold"
          style={{ color: "var(--hb-text-hi)" }}
        >
          {label}
          {saving && (
            <span
              className="ml-2 text-[10px]"
              style={{ color: "var(--hb-text-dim)" }}
            >
              Сохранение…
            </span>
          )}
        </p>
        <p
          className="mt-1 text-[11px] leading-relaxed"
          style={{ color: "var(--hb-text-dim)" }}
        >
          {help}
        </p>
      </div>
      <label className="hb-toggle shrink-0">
        <input
          type="checkbox"
          checked={value}
          onChange={onClick}
          disabled={saving}
        />
        <span className="hb-toggle-track">
          <span className="hb-toggle-thumb" />
        </span>
      </label>
    </div>
  );
}

