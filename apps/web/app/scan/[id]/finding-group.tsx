"use client";

import { useState } from "react";
import { FindingRow } from "./finding-row";

type Finding = {
  id: string;
  title: string;
  description: string;
  severity: string;
  source_engine: string;
  file: string | null;
  line: number | null;
  confidence: number;
  dismissed: boolean;
  poc_validated?: boolean;
  poc_path?: string | null;
  metadata?: {
    similar_incidents?: Array<{
      incident_id: string;
      title: string;
      url: string;
      source: string;
      loss_usd: number | null;
      published_at: string;
      similarity: number;
    }>;
  } | null;
};

const SEV_ORDER: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
  info: 4,
};

const SEV_COLOR: Record<string, string> = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#facc15",
  low: "#4ade80",
  info: "#8bb88b",
};

export function groupFindings(findings: Finding[]) {
  const map = new Map<string, Finding[]>();
  for (const f of findings) {
    const key = f.title;
    const arr = map.get(key) ?? [];
    arr.push(f);
    map.set(key, arr);
  }
  const groups = [...map.entries()].map(([title, items]) => ({
    title,
    items,
    topSeverity: items.reduce(
      (best, f) => ((SEV_ORDER[f.severity] ?? 99) < (SEV_ORDER[best] ?? 99) ? f.severity : best),
      items[0].severity,
    ),
  }));
  groups.sort(
    (a, b) => (SEV_ORDER[a.topSeverity] ?? 99) - (SEV_ORDER[b.topSeverity] ?? 99),
  );
  return groups;
}

export function FindingGroups({
  findings,
  animationOffset = 0,
}: {
  findings: Finding[];
  animationOffset?: number;
}) {
  const groups = groupFindings(findings);

  return (
    <ul className="space-y-3">
      {groups.map((g, gi) =>
        g.items.length === 1 ? (
          <li
            key={g.items[0].id}
            className="animate-fade-in-up"
            style={{ animationDelay: `${(animationOffset + gi) * 60}ms` }}
          >
            <FindingRow finding={g.items[0]} />
          </li>
        ) : (
          <li
            key={g.title}
            className="animate-fade-in-up"
            style={{ animationDelay: `${(animationOffset + gi) * 60}ms` }}
          >
            <CollapsibleGroup group={g} />
          </li>
        ),
      )}
    </ul>
  );
}

function CollapsibleGroup({
  group,
}: {
  group: { title: string; items: Finding[]; topSeverity: string };
}) {
  const [open, setOpen] = useState(false);
  const color = SEV_COLOR[group.topSeverity] ?? "#8bb88b";

  return (
    <div className="glass-card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-5 py-4 text-left"
        aria-expanded={open}
      >
        <span
          className="rounded-md px-2 py-0.5 text-xs font-bold"
          style={{
            backgroundColor: color + "18",
            color,
            border: `1px solid ${color}44`,
          }}
        >
          {group.items.length}x
        </span>
        <span className="flex-1 truncate font-medium text-[#d4ffd4]">
          {group.title}
        </span>
        <span className="text-xs text-[#547654]">
          {group.items.length} совпадений
        </span>
        <svg
          className={`h-4 w-4 text-[#547654] transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M5.23 7.21a.75.75 0 011.06.02L10 11.06l3.71-3.83a.75.75 0 111.08 1.04l-4.25 4.38a.75.75 0 01-1.08 0L5.21 8.27a.75.75 0 01.02-1.06z"
            clipRule="evenodd"
          />
        </svg>
      </button>
      {open && (
        <div className="space-y-2 border-t border-[#1a2e1a] p-3">
          {group.items.map((f) => (
            <FindingRow key={f.id} finding={f} />
          ))}
        </div>
      )}
    </div>
  );
}
