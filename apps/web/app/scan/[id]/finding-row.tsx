"use client";

import { useState } from "react";

type SimilarIncident = {
  incident_id: string;
  title: string;
  url: string;
  source: string;
  loss_usd: number | null;
  published_at: string;
  similarity: number;
};

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
    metadata?: {
      similar_incidents?: SimilarIncident[];
      engines?: string[];
      dedup_merged_count?: number;
      confirms?: string[];
      network_adjustment?: { network: string; original_confidence: number; multiplier: number };
    } | null;
  };
}

const SEVERITY_STYLE: Record<
  string,
  { label: string; color: string; glow: string }
> = {
  critical: {
    label: "CRITICAL",
    color: "#ef4444",
    glow: "shadow-[0_0_8px_rgba(239,68,68,0.4)]",
  },
  high: {
    label: "HIGH",
    color: "#f97316",
    glow: "shadow-[0_0_8px_rgba(249,115,22,0.3)]",
  },
  medium: {
    label: "MEDIUM",
    color: "#facc15",
    glow: "shadow-[0_0_8px_rgba(250,204,21,0.3)]",
  },
  low: {
    label: "LOW",
    color: "#4ade80",
    glow: "shadow-[0_0_8px_rgba(74,222,128,0.3)]",
  },
  info: {
    label: "INFO",
    color: "#8bb88b",
    glow: "",
  },
};

export function FindingRow({ finding }: FindingRowProps) {
  const [open, setOpen] = useState(false);
  const sev = SEVERITY_STYLE[finding.severity] ?? SEVERITY_STYLE.info;
  const confidencePct = Math.round(finding.confidence * 100);

  return (
    <div className="glass-card overflow-hidden transition-all duration-200">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-5 py-4 text-left"
        aria-expanded={open}
      >
        {/* Severity Badge */}
        <span
          className={`rounded-md px-2.5 py-1 text-xs font-bold ${sev.glow}`}
          style={{
            backgroundColor: sev.color + "18",
            color: sev.color,
            border: `1px solid ${sev.color}44`,
          }}
        >
          {sev.label}
        </span>

        {/* PoC Validated Badge */}
        {finding.poc_validated && (
          <span className="flex items-center gap-1 rounded-md border border-[#4ade80]/30 bg-[#4ade80]/10 px-2 py-0.5 text-xs font-semibold text-[#4ade80] shadow-[0_0_6px_rgba(74,222,128,0.2)]">
            <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                clipRule="evenodd"
              />
            </svg>
            PoC
          </span>
        )}

        {/* Multi-engine confirmation badge */}
        {(finding.metadata?.engines?.length ?? 0) > 1 && (
          <span className="flex items-center gap-1 rounded-md border border-blue-400/30 bg-blue-400/10 px-2 py-0.5 text-xs font-semibold text-blue-400">
            {finding.metadata!.engines!.length}x
          </span>
        )}

        {/* Title */}
        <span className="flex-1 truncate font-medium text-[#d4ffd4]">
          {finding.title}
        </span>

        {/* Source Engine Chip */}
        <span className="rounded border border-[#547654]/50 bg-[#0a0e0a] px-2 py-0.5 font-mono text-xs text-[#8bb88b]">
          {finding.source_engine}
        </span>

        {/* Confidence mini bar */}
        <span className="flex items-center gap-1.5 text-xs text-[#547654]">
          <span className="h-1.5 w-8 overflow-hidden rounded-full bg-[#1a2e1a]">
            <span
              className="block h-full rounded-full bg-[#4ade80]"
              style={{ width: `${confidencePct}%` }}
            />
          </span>
          {confidencePct}%
        </span>

        {/* Chevron */}
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
        <div className="border-t border-[#1a2e1a] px-5 py-4">
          {/* Description */}
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-[#8bb88b]">
            {finding.description || "No description provided by analyzer."}
          </p>

          {/* Metadata grid */}
          <div className="mt-4 flex flex-wrap gap-4 text-xs">
            {finding.file && (
              <div className="flex items-center gap-1.5">
                <span className="text-[#547654]">File:</span>
                <span className="font-mono text-[#8bb88b]">
                  {finding.file}
                  {finding.line != null && `:${finding.line}`}
                </span>
              </div>
            )}
            <div className="flex items-center gap-1.5">
              <span className="text-[#547654]">Engine:</span>
              <span className="font-mono text-[#8bb88b]">
                {(finding.metadata?.engines?.length ?? 0) > 1
                  ? finding.metadata!.engines!.join(" + ")
                  : finding.source_engine}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[#547654]">Confidence:</span>
              <span className="font-mono text-[#4ade80]">{confidencePct}%</span>
              {finding.metadata?.network_adjustment && (
                <span className="text-blue-400" title={`Network ${finding.metadata.network_adjustment.network}: x${finding.metadata.network_adjustment.multiplier}`}>
                  (adj.)
                </span>
              )}
            </div>
          </div>

          {/* Cross-engine confirmations */}
          {(finding.metadata?.confirms?.length ?? 0) > 0 && (
            <div className="mt-3 rounded-lg border border-blue-400/20 bg-blue-400/5 p-3">
              <p className="mb-2 text-xs font-semibold text-blue-400">
                Подтверждено другими движками:
              </p>
              {finding.metadata!.confirms!.map((c, i) => (
                <p key={i} className="mb-1 text-xs leading-relaxed text-[#8bb88b]">
                  {c}
                </p>
              ))}
            </div>
          )}

          {/* Similar Incidents */}
          {(finding.metadata?.similar_incidents?.length ?? 0) > 0 && (
            <SimilarIncidents incidents={finding.metadata!.similar_incidents!} />
          )}
        </div>
      )}
    </div>
  );
}

function SimilarIncidents({ incidents }: { incidents: SimilarIncident[] }) {
  return (
    <div className="mt-4 border-t border-[#1a2e1a] pt-4">
      <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[#8bb88b]">
        Similar past incidents
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        {incidents.map((i) => {
          const lossStr =
            i.loss_usd == null
              ? ""
              : i.loss_usd >= 1_000_000
                ? `$${(i.loss_usd / 1_000_000).toFixed(1)}M`
                : `$${(i.loss_usd / 1_000).toFixed(0)}K`;
          return (
            <a
              key={i.incident_id}
              href={i.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex flex-col rounded-lg border border-[#1a2e1a] bg-[#0a0e0a]/50 p-3 transition-colors hover:border-[#4ade80]/30"
            >
              <div className="flex items-center justify-between">
                <span className="rounded bg-[#4ade80]/10 px-1.5 py-0.5 font-mono text-xs text-[#4ade80]">
                  {Math.round(i.similarity * 100)}% match
                </span>
                {lossStr && (
                  <span className="text-xs font-semibold text-red-400">
                    {lossStr}
                  </span>
                )}
              </div>
              <span className="mt-1.5 text-xs text-[#d4ffd4] group-hover:text-[#4ade80]">
                {i.title}
              </span>
              <span className="mt-1 text-xs text-[#547654]">
                {i.source} · {new Date(i.published_at).getFullYear()}
              </span>
            </a>
          );
        })}
      </div>
    </div>
  );
}
