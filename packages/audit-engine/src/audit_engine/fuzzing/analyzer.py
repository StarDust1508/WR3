"""LLM analyzes counterexamples: real bug or invariant artifact?

Random fuzzing often "breaks" invariants for the wrong reason — the invariant
itself encoded an assumption that doesn't actually hold under valid usage. We
let the LLM decide:
    - REAL:      this counterexample exposes a genuine bug; emit a Finding.
    - ARTIFACT:  invariant was wrong; do not emit a Finding.
    - UNCLEAR:   keep the case but tag as low confidence.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal

import structlog

from audit_engine.fuzzing.types import Counterexample, FuzzInvariant
from audit_engine.llm import LLMRequest, LLMRouter, Sensitivity

logger = structlog.get_logger()


@dataclass
class AnalysisVerdict:
    """Per-counterexample verdict + extracted human-readable explanation."""

    invariant_name: str
    verdict: Literal["real", "artifact", "unclear"]
    title: str
    description: str
    rationale: str


_SYSTEM = """You are a senior smart-contract security auditor reviewing
counterexamples that a fuzzer produced against an invariant.

For each (invariant, counterexample) pair, decide:
  - real:     the counterexample is a genuine bug. Provide a title and a
              2-3 sentence description suitable for a finding.
  - artifact: the invariant was poorly specified; the counterexample is not
              a bug. Explain in one sentence why.
  - unclear:  not enough context to decide.

Output JSON only, no fences:
{
  "verdicts": [
    {"invariant": "invariant_xxx",
     "verdict": "real" | "artifact" | "unclear",
     "title": "<short title for the finding>",
     "description": "<2-3 sentences>",
     "rationale": "<one sentence>"}
  ]
}
"""


_USER_TEMPLATE = """SOURCE CODE:
```solidity
{source}
```

INVARIANTS:
{invariants_json}

COUNTEREXAMPLES (truncated):
{counterexamples_json}

Classify each counterexample. Output JSON only.
"""


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


class CounterexampleAnalyzer:
    def __init__(
        self,
        llm: LLMRouter | None = None,
        *,
        max_source_chars: int = 24_000,
        max_trace_chars: int = 1500,
    ) -> None:
        self.llm = llm or LLMRouter()
        self.max_source_chars = max_source_chars
        self.max_trace_chars = max_trace_chars

    async def analyze(
        self,
        *,
        source: str,
        invariants: list[FuzzInvariant],
        counterexamples: list[Counterexample],
    ) -> list[AnalysisVerdict]:
        if not counterexamples:
            return []

        invs_json = json.dumps(
            [{"name": i.name, "rationale": i.rationale} for i in invariants],
            ensure_ascii=False,
            indent=2,
        )
        ces_json = json.dumps(
            [
                {
                    "invariant": ce.invariant_name,
                    "trace": ce.call_trace[: self.max_trace_chars],
                    "reason": ce.reason or "",
                }
                for ce in counterexamples
            ],
            ensure_ascii=False,
            indent=2,
        )

        try:
            raw = await self.llm.complete(
                LLMRequest(
                    messages=[
                        {"role": "system", "content": _SYSTEM},
                        {
                            "role": "user",
                            "content": _USER_TEMPLATE.format(
                                source=source[: self.max_source_chars],
                                invariants_json=invs_json,
                                counterexamples_json=ces_json,
                            ),
                        },
                    ],
                    sensitivity=Sensitivity.HIGH,
                    temperature=0.1,
                    max_tokens=3000,
                )
            )
        except Exception as e:
            logger.warning("counterexample.llm_failed", error=str(e))
            # Best-effort fallback: mark everything unclear so the pipeline
            # still surfaces the broken invariants rather than dropping them.
            return [
                AnalysisVerdict(
                    invariant_name=ce.invariant_name,
                    verdict="unclear",
                    title=f"Invariant {ce.invariant_name} broke (unanalyzed)",
                    description=ce.call_trace[:600] or "no trace",
                    rationale="LLM analyzer unavailable",
                )
                for ce in counterexamples
            ]

        return self._parse(raw, fallback=counterexamples)

    def _parse(
        self, raw: str, *, fallback: list[Counterexample]
    ) -> list[AnalysisVerdict]:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.DOTALL)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            m = _JSON_BLOCK.search(cleaned)
            if not m:
                return [
                    AnalysisVerdict(
                        invariant_name=ce.invariant_name,
                        verdict="unclear",
                        title=f"Invariant {ce.invariant_name} broke",
                        description=ce.call_trace[:600],
                        rationale="parser failed",
                    )
                    for ce in fallback
                ]
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                return []

        if not isinstance(data, dict):
            return []
        verdicts_raw = data.get("verdicts") or []
        if not isinstance(verdicts_raw, list):
            return []

        out: list[AnalysisVerdict] = []
        for v in verdicts_raw:
            if not isinstance(v, dict):
                continue
            name = str(v.get("invariant") or "").strip()
            if not name:
                continue
            verdict = (v.get("verdict") or "unclear").lower().strip()
            if verdict not in ("real", "artifact", "unclear"):
                verdict = "unclear"
            out.append(
                AnalysisVerdict(
                    invariant_name=name,
                    verdict=verdict,  # type: ignore[arg-type]
                    title=str(v.get("title") or f"Invariant {name} broke").strip(),
                    description=str(v.get("description") or "").strip(),
                    rationale=str(v.get("rationale") or "").strip(),
                )
            )
        return out
