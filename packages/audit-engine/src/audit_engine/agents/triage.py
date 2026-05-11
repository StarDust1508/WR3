"""LLM triage agent — pass 1 of the multi-agent layer.

Input: raw findings + source code (+ optional Solodit RAG context).
Output: same findings, but each annotated with one of:
    - keep   (severity unchanged, confidence may rise)
    - reclassify (severity changed up or down, with rationale)
    - dismiss (false positive, with rationale)

Design choices:
- Single JSON-mode call per audit. We pack all findings into one prompt
  rather than one call per finding — for typical scans (<30 raw findings)
  this is faster and cheaper, and the model can spot cross-finding
  patterns (e.g. one access-control gate covers three "tx.origin" hits).
- Robust to LLM failures: any non-parseable response leaves findings
  untouched. The pipeline never aborts on triage error.
- LOW-risk findings (severity=info, severity=low with confidence > 0.8)
  skip triage to save tokens — they go straight through.
"""

from __future__ import annotations

import json
import re

import structlog

from audit_engine.knowledge import SoloditClient
from audit_engine.llm import LLMRequest, LLMRouter, Sensitivity
from audit_engine.types import Finding, Severity

logger = structlog.get_logger()

_TRIAGE_SYSTEM_PROMPT = """You are a senior smart-contract security auditor performing triage.

You receive:
  1. The source code of a Solidity contract.
  2. Optional similar findings from the Solodit database, for reference.
  3. A list of raw findings from static analyzers (Aderyn / Wake / Slither /
     baseline regex). Each has an id, title, severity guess, and confidence.

For each finding, decide one of:
  - keep: the finding is real and the severity guess is correct
  - reclassify: real but wrong severity (give new severity)
  - dismiss: false positive (give a short reason rooted in the code)

Severity vocabulary: info, low, medium, high, critical.

Be conservative: when in doubt, "keep". Only "dismiss" when you can point to
specific code that makes the pattern safe (e.g. a modifier, a require check,
an upstream constraint).

Respond ONLY as a JSON object, no preamble, no markdown fences:
{
  "decisions": [
    {"id": "<finding id>", "action": "keep" | "reclassify" | "dismiss",
     "new_severity": "<severity if reclassify>",
     "rationale": "<one sentence>"}
  ]
}
"""


class TriageOrchestrator:
    """Single-call LLM triage. Designed for Stage 3 of the pipeline."""

    def __init__(
        self,
        llm: LLMRouter | None = None,
        solodit: SoloditClient | None = None,
        *,
        max_source_chars: int = 24_000,
        max_findings_in_prompt: int = 40,
    ) -> None:
        self.llm = llm or LLMRouter()
        self.solodit = solodit or SoloditClient()
        self.max_source_chars = max_source_chars
        self.max_findings_in_prompt = max_findings_in_prompt

    async def run(self, findings: list[Finding], *, source: str) -> list[Finding]:
        triageable = [f for f in findings if self._needs_triage(f)]
        if not triageable:
            logger.info("triage.skipped.nothing_to_triage", total=len(findings))
            return findings

        rag_context = await self._fetch_rag_context(triageable)

        prompt = self._build_prompt(
            source=source[: self.max_source_chars],
            findings=triageable[: self.max_findings_in_prompt],
            rag=rag_context,
        )

        try:
            raw = await self.llm.complete(
                LLMRequest(
                    messages=[
                        {"role": "system", "content": _TRIAGE_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    sensitivity=Sensitivity.HIGH,
                    temperature=0.1,
                    max_tokens=4096,
                )
            )
        except Exception as e:
            logger.warning("triage.llm_call_failed", error=str(e))
            return findings

        decisions = self._parse_decisions(raw)
        if not decisions:
            logger.warning("triage.parse_failed", raw_head=raw[:200])
            return findings

        return self._apply_decisions(findings, decisions)

    def _needs_triage(self, f: Finding) -> bool:
        if f.dismissed:
            return False
        # Skip cheap noise — INFO and high-confidence LOW are kept as-is.
        if f.severity == Severity.INFO:
            return False
        return not (f.severity == Severity.LOW and f.confidence >= 0.8)

    async def _fetch_rag_context(self, findings: list[Finding]) -> str:
        # Use distinct titles as queries; cap to 3 to control latency.
        seen: set[str] = set()
        entries: list[str] = []
        for f in findings:
            key = f.title.lower()
            if key in seen:
                continue
            seen.add(key)
            if len(seen) > 3:
                break
            try:
                hits = await self.solodit.search(f.title, limit=2)
            except Exception:
                hits = []
            for h in hits:
                entries.append(
                    f"- [{h.severity}] {h.title} ({h.source_firm or 'unknown'}): {h.body[:280]}"
                )
        if not entries:
            return ""
        return "Solodit RAG context (similar past findings):\n" + "\n".join(entries[:8])

    def _build_prompt(
        self, *, source: str, findings: list[Finding], rag: str
    ) -> str:
        findings_json = json.dumps(
            [
                {
                    "id": f.id,
                    "title": f.title,
                    "severity": f.severity.value,
                    "engine": f.source_engine,
                    "confidence": round(f.confidence, 2),
                    "line": f.line,
                    "description": f.description[:600],
                }
                for f in findings
            ],
            ensure_ascii=False,
            indent=2,
        )
        parts = [
            "SOURCE CODE:",
            "```solidity",
            source,
            "```",
            "",
        ]
        if rag:
            parts += [rag, ""]
        parts += [
            "RAW FINDINGS TO TRIAGE:",
            findings_json,
        ]
        return "\n".join(parts)

    _JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

    def _parse_decisions(self, raw: str) -> list[dict] | None:
        # LLMs sometimes wrap JSON in fences despite instructions.
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.DOTALL)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            m = self._JSON_BLOCK.search(cleaned)
            if not m:
                return None
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                return None

        decisions = data.get("decisions") if isinstance(data, dict) else None
        if not isinstance(decisions, list):
            return None
        return [d for d in decisions if isinstance(d, dict)]

    def _apply_decisions(
        self, findings: list[Finding], decisions: list[dict]
    ) -> list[Finding]:
        by_id = {d.get("id"): d for d in decisions if d.get("id")}

        result: list[Finding] = []
        for f in findings:
            d = by_id.get(f.id)
            if d is None:
                result.append(f)
                continue

            action = (d.get("action") or "").lower()
            rationale = (d.get("rationale") or "").strip()

            if action == "dismiss":
                result.append(
                    f.model_copy(
                        update={
                            "dismissed": True,
                            "dismissed_reason": rationale or "LLM triage dismissed",
                        }
                    )
                )
            elif action == "reclassify":
                new_sev_raw = (d.get("new_severity") or "").lower()
                try:
                    new_sev = Severity(new_sev_raw)
                except ValueError:
                    result.append(f)
                    continue
                result.append(
                    f.model_copy(
                        update={
                            "severity": new_sev,
                            "confidence": min(1.0, f.confidence + 0.1),
                            "metadata": {**f.metadata, "triage_rationale": rationale},
                        }
                    )
                )
            else:  # keep / unknown
                result.append(
                    f.model_copy(
                        update={
                            "confidence": min(1.0, f.confidence + 0.1),
                            "metadata": {**f.metadata, "triage_rationale": rationale},
                        }
                    )
                )

        return result
