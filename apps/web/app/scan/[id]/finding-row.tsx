"use client";

import { useState } from "react";

interface FindingRowProps {
  finding: {
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
  };
}

const SEVERITY_STYLE: Record<string, { label: string; bg: string; text: string }> = {
  critical: { label: "CRITICAL", bg: "bg-red-600", text: "text-white" },
  high: { label: "HIGH", bg: "bg-red-100 dark:bg-red-950", text: "text-red-800 dark:text-red-200" },
  medium: { label: "MED", bg: "bg-amber-100 dark:bg-amber-950", text: "text-amber-800 dark:text-amber-200" },
  low: { label: "LOW", bg: "bg-blue-100 dark:bg-blue-950", text: "text-blue-800 dark:text-blue-200" },
  info: { label: "INFO", bg: "bg-zinc-100 dark:bg-zinc-800", text: "text-zinc-600 dark:text-zinc-400" },
};

export function FindingRow({ finding }: FindingRowProps) {
  const [open, setOpen] = useState(false);
  const sev = SEVERITY_STYLE[finding.severity] ?? SEVERITY_STYLE.info;

  return (
    <li className="rounded-md border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-zinc-50 dark:hover:bg-zinc-900"
        aria-expanded={open}
      >
        <span className={`rounded px-2 py-0.5 text-xs font-semibold ${sev.bg} ${sev.text}`}>
          {sev.label}
        </span>
        {finding.poc_validated && (
          <span
            className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
            title="Foundry PoC подтвердил эксплойт"
          >
            PoC ✓
          </span>
        )}
        <span className="flex-1 truncate font-medium">{finding.title}</span>
        <span className="font-mono text-xs text-zinc-500">
          {finding.source_engine}
          {finding.line != null && `:${finding.line}`}
        </span>
        <svg
          className={`h-4 w-4 text-zinc-400 transition-transform ${open ? "rotate-180" : ""}`}
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
        <div className="border-t border-zinc-100 px-4 py-3 text-sm dark:border-zinc-800">
          <p className="whitespace-pre-wrap text-zinc-700 dark:text-zinc-300">
            {finding.description || "No description provided by analyzer."}
          </p>
          <dl className="mt-3 grid grid-cols-[120px_1fr] gap-1 text-xs text-zinc-500">
            {finding.file && (
              <>
                <dt>File</dt>
                <dd className="font-mono">{finding.file}</dd>
              </>
            )}
            {finding.line != null && (
              <>
                <dt>Line</dt>
                <dd className="font-mono">{finding.line}</dd>
              </>
            )}
            <dt>Confidence</dt>
            <dd>{Math.round(finding.confidence * 100)}%</dd>
            <dt>Engine</dt>
            <dd>{finding.source_engine}</dd>
          </dl>
        </div>
      )}
    </li>
  );
}
