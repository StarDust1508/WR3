// Shared types between web (Next.js) and api (FastAPI).
// Mirrors audit_engine.types — keep in sync via codegen later.

export type Network = "ethereum" | "base" | "arbitrum" | "bsc" | "solana";

export type Severity = "info" | "low" | "medium" | "high" | "critical";

export type Tier = "red" | "yellow" | "green" | "blue";

export type Stage =
  | "queued"
  | "static"
  | "triage"
  | "poc"
  | "fuzzing"
  | "scoring"
  | "done"
  | "error";

export interface Finding {
  id: string;
  title: string;
  description: string;
  severity: Severity;
  source_engine: string;
  file?: string | null;
  line?: number | null;
  swc_id?: string | null;
  cwe_id?: string | null;
  confidence: number;
  dismissed: boolean;
  dismissed_reason?: string | null;
  poc_path?: string | null;
  poc_validated: boolean;
}

export interface ScoreAxis {
  name: string;
  weight: number;
  score: number;
  rationale: string;
}

export interface AuditReport {
  address: string;
  network: Network;
  score: number;
  tier: Tier;
  axes: ScoreAxis[];
  findings: Finding[];
  engine_versions: Record<string, string>;
  audit_duration_seconds?: number | null;
  disclaimer: string;
}

export interface ScanProgress {
  stage: Stage;
  progress: number;
  message?: string;
  score?: number;
  tier?: Tier;
}

export interface ScanRequest {
  address: string;
  network: Network;
  source_code?: string;
}

export interface ScanResponse {
  job_id: string;
  status: "queued";
}

export const TRAFFIC_LIGHT: Record<Tier, { label: string; color: string }> = {
  red: { label: "High risk", color: "#dc2626" },
  yellow: { label: "Caution", color: "#ca8a04" },
  green: { label: "Acceptable", color: "#16a34a" },
  blue: { label: "Excellent", color: "#2563eb" },
};
