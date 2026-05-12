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
 * Owner panel. Toggles are real — flipping them changes how the pipeline
 * runs the next time the user starts a scan. Backed by user.preferences
 * JSONB on the server.
 *
 * Toggles that are not yet wired (continuous_monitoring) are marked
 * "not active yet" in the UI so we don't lie.
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
        ← back
      </Link>

      <h1
        className="mt-4 text-sm hb-prompt"
        style={{ color: "var(--hb-text-hi)" }}
      >
        owner config<span className="hb-cursor" />
      </h1>
      <p className="mt-1 text-[11px]" style={{ color: "var(--hb-text-muted)" }}>
        // these toggles change what the pipeline actually does on next scan
      </p>

      {error && (
        <p className="mt-3 text-xs" style={{ color: "var(--hb-error)" }}>
          <span>ERR </span>{error}
        </p>
      )}

      {prefs === null ? (
        <p className="mt-8 text-center text-xs hb-prompt">
          loading<span className="hb-cursor" />
        </p>
      ) : (
        <section className="mt-5 flex flex-col gap-2">
          <Toggle
            label="auto-poc"
            help="Stage 4: Foundry PoC retry-loop for HIGH/CRITICAL findings. Uses LLM credits + forge."
            value={prefs.auto_poc}
            saving={savingKey === "auto_poc"}
            onClick={() => toggle("auto_poc")}
          />
          <Toggle
            label="auto-fuzzing"
            help="Stage 5: AI-generated invariants run through medusa/forge invariant. Most expensive stage."
            value={prefs.auto_fuzzing}
            saving={savingKey === "auto_fuzzing"}
            onClick={() => toggle("auto_fuzzing")}
          />
          <Toggle
            label="multi-agent triage"
            help="Stage 3: 4 parallel Claude agents (severity / FP / business / cross-contract). Off = single-call triage."
            value={prefs.multi_agent_triage}
            saving={savingKey === "multi_agent_triage"}
            onClick={() => toggle("multi_agent_triage")}
          />
          <Toggle
            label="continuous monitoring"
            help="24/7 re-scan of your watched contracts on upgrades, ownership changes, anomalies."
            value={prefs.continuous_monitoring}
            saving={savingKey === "continuous_monitoring"}
            onClick={() => toggle("continuous_monitoring")}
            notActive
          />
          <Toggle
            label="anonymous in public"
            help="Hide your handle from the public leaderboard / scans index."
            value={prefs.anonymous_in_public}
            saving={savingKey === "anonymous_in_public"}
            onClick={() => toggle("anonymous_in_public")}
            notActive
          />
        </section>
      )}

      <section className="mt-8">
        <h2 className="tg-hint mb-2">behaviour summary</h2>
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
  notActive,
}: {
  label: string;
  help: string;
  value: boolean;
  saving: boolean;
  onClick: () => void;
  notActive?: boolean;
}) {
  return (
    <div className="tg-card flex items-start gap-3">
      <div className="min-w-0 flex-1">
        <p
          className="text-xs font-bold"
          style={{ color: "var(--hb-text-hi)" }}
        >
          {label}
          {notActive && (
            <span
              className="ml-2 tg-chip sev-chip-info"
              title="Toggle persists, but the underlying feature is not wired up yet."
            >
              not active yet
            </span>
          )}
          {saving && (
            <span className="ml-2 text-[10px]" style={{ color: "var(--hb-text-muted)" }}>
              saving…
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
    `  "continuous_monitoring": ${p.continuous_monitoring},   // dormant`,
    `  "anonymous_in_public":   ${p.anonymous_in_public}    // dormant`,
    "}",
  ];
  return lines.join("\n");
}
