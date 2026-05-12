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
      <Link href="/tg" className="text-xs" style={{ color: "var(--hb-text-dim)" }}>
        ← назад
      </Link>

      <h1
        className="mt-4 text-sm hb-prompt"
        style={{ color: "var(--hb-text-hi)" }}
      >
        настройки владельца<span className="hb-cursor" />
      </h1>
      <p className="mt-1 text-[11px]" style={{ color: "var(--hb-text-muted)" }}>
        // переключатели меняют поведение пайплайна при следующем скане
      </p>

      {error && (
        <p className="mt-3 text-xs" style={{ color: "var(--hb-error)" }}>
          <span>ERR </span>{error}
        </p>
      )}

      {prefs === null ? (
        <p className="mt-8 text-center text-xs hb-prompt">
          загрузка<span className="hb-cursor" />
        </p>
      ) : (
        <section className="mt-5 flex flex-col gap-2">
          <Toggle
            label="auto-poc"
            help="Стадия 4: Foundry PoC retry-loop для HIGH/CRITICAL находок. Расходует LLM-токены + forge."
            value={prefs.auto_poc}
            saving={savingKey === "auto_poc"}
            onClick={() => toggle("auto_poc")}
          />
          <Toggle
            label="auto-fuzzing"
            help="Стадия 5: AI-сгенерированные инварианты через medusa/forge invariant. Самая дорогая стадия."
            value={prefs.auto_fuzzing}
            saving={savingKey === "auto_fuzzing"}
            onClick={() => toggle("auto_fuzzing")}
          />
          <Toggle
            label="multi-agent triage"
            help="Стадия 3: 4 параллельных Claude-агента (severity / FP / business / cross-contract). Off = один LLM-вызов."
            value={prefs.multi_agent_triage}
            saving={savingKey === "multi_agent_triage"}
            onClick={() => toggle("multi_agent_triage")}
          />
          <Toggle
            label="мониторинг 24/7"
            help="Каждые 6 часов проверяем твои контракты через Etherscan: alert при смене source code, владельца или upgrade impl. Без LLM-токенов."
            value={prefs.continuous_monitoring}
            saving={savingKey === "continuous_monitoring"}
            onClick={() => toggle("continuous_monitoring")}
          />
          <Toggle
            label="анонимность в публичном"
            help="Скрыть твой handle из публичного лидерборда / индекса сканов."
            value={prefs.anonymous_in_public}
            saving={savingKey === "anonymous_in_public"}
            onClick={() => toggle("anonymous_in_public")}
          />
        </section>
      )}

      <section className="mt-8">
        <h2 className="tg-hint mb-2">итог конфигурации</h2>
        <pre
          className="tg-card text-[11px]"
          style={{
            color: "var(--hb-text-dim)",
            whiteSpace: "pre-wrap",
            margin: 0,
          }}
        >
{prefs ? renderConfigDump(prefs) : "$ ..."}
        </pre>
      </section>
    </main>
  );
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
          className="text-xs font-bold"
          style={{ color: "var(--hb-text-hi)" }}
        >
          {label}
          {saving && (
            <span className="ml-2 text-[10px]" style={{ color: "var(--hb-text-muted)" }}>
              сохраняю…
            </span>
          )}
        </p>
        <p className="mt-1 text-[11px]" style={{ color: "var(--hb-text-muted)" }}>
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

function renderConfigDump(p: Prefs): string {
  const lines = [
    "$ wr3 config dump",
    "{",
    `  "auto_poc":              ${p.auto_poc},`,
    `  "auto_fuzzing":          ${p.auto_fuzzing},`,
    `  "multi_agent_triage":    ${p.multi_agent_triage},`,
    `  "continuous_monitoring": ${p.continuous_monitoring},`,
    `  "anonymous_in_public":   ${p.anonymous_in_public}`,
    "}",
  ];
  return lines.join("\n");
}
