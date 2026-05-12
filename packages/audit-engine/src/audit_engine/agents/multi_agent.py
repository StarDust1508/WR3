"""Multi-agent triage layer — Trident Arena pattern.

Four sub-agents run in parallel against the same raw findings + source:

    SeverityClassifier  — re-ranks severity; reads context, has authority on
                          severity normalization across engines.
    FalsePositiveFilter — looks for arguments to dismiss; does NOT touch
                          severity. Its only job is `dismiss` or `keep`.
    BusinessLogicReasoner — emits NEW findings that pattern-matchers miss
                          (logical bugs, broken invariants). May also flag
                          existing findings as confirmed.
    CrossContractAnalyzer — same shape but focused on proxies, delegatecalls,
                          inter-contract trust.

A consensus layer merges the four reports into a final findings list:
    - For existing findings: severity from SeverityClassifier wins, but
      FalsePositiveFilter can dismiss if SeverityClassifier downranks to
      low/info too. BusinessLogic/CrossContract can flip a dismissal back
      to keep if they cite specific evidence.
    - For NEW findings (proposed by Business/CrossContract): added with
      confidence 0.6, source_engine="llm-business-logic"/"llm-cross-contract".

Reference benchmark (TZ.md §4.5): Trident Arena hit 70% recall vs 33% for
GPT-5.2 alone, 86% -> 26% FP rate via cross-checking. wr3 target: ≥75%.

Design notes:
- Parallel via anyio task group; one LLM call per sub-agent.
- Total: 4 calls per audit instead of 1 (TZ.md §3.1 cost note). Triage is
  the most expensive stage; later, a "cheap mode" can fall back to the
  single-call TriageOrchestrator in triage.py.
- Robust to per-agent failure: a crashed agent contributes nothing rather
  than aborting consensus.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import anyio
import structlog

from audit_engine.llm import LLMRequest, LLMRouter, Sensitivity
from audit_engine.types import Finding, Severity

logger = structlog.get_logger()


# --- Shared structures -------------------------------------------------------


@dataclass
class AgentDecision:
    """One agent's verdict on a single existing finding."""

    finding_id: str
    action: str  # keep | reclassify | dismiss | confirm
    new_severity: Severity | None = None
    rationale: str = ""


@dataclass
class ProposedFinding:
    """A NEW finding that a generative agent surfaced (not from static engines)."""

    title: str
    description: str
    severity: Severity
    line: int | None = None
    rationale: str = ""


@dataclass
class AgentReport:
    """One agent's full output for an audit."""

    agent: str
    decisions: list[AgentDecision] = field(default_factory=list)
    proposed: list[ProposedFinding] = field(default_factory=list)
    failed: bool = False
    error: str | None = None


# --- Sub-agent prompts -------------------------------------------------------


_SEVERITY_SYSTEM = """You are a smart-contract security auditor whose only job
is to normalize severity across findings from different static engines.

Severity vocabulary: info, low, medium, high, critical.

For each finding, decide:
  - keep        — severity guess is correct
  - reclassify  — severity wrong; supply new_severity

Be conservative on dismissal — that is not your job (another agent does FP
filtering). Focus on whether the severity assigned matches the actual impact
visible in the code.

Respond ONLY as a JSON object, no preamble, no markdown fences:
{
  "decisions": [
    {"id": "<finding id>", "action": "keep" | "reclassify",
     "new_severity": "<severity if reclassify>",
     "rationale": "<one sentence>"}
  ]
}
"""

_FP_SYSTEM = """You are a smart-contract security auditor whose ONLY job is
to flag false positives.

Severity is irrelevant for you. For each finding, decide:
  - keep    — the finding is real
  - dismiss — the finding is a false positive

You may ONLY dismiss when you can point to specific code that proves the
pattern is safe (e.g. a modifier upstream, a require check, an upstream
constraint, the file is a test/mock, etc). Vague rationales ("looks fine")
must default to keep.

Respond ONLY as a JSON object, no preamble, no markdown fences:
{
  "decisions": [
    {"id": "<finding id>", "action": "keep" | "dismiss",
     "rationale": "<one sentence with code reference>"}
  ]
}
"""

_BIZLOGIC_SYSTEM = """You are a smart-contract security auditor specialized in
business-logic flaws — bugs that pattern-matchers miss. Examples: broken
invariants, accounting errors, oracle staleness, fee-on-transfer mishandling,
sandwich-vulnerable flows, slippage missing, reward-claim race conditions,
front-running paths, MEV exposure.

You do TWO things:
  1) Confirm existing findings whose root cause is a business-logic flaw,
     by emitting action="confirm" with a specific rationale.
  2) Propose NEW findings that the static engines would not catch.

Respond ONLY as a JSON object, no preamble, no markdown fences:
{
  "decisions": [
    {"id": "<finding id>", "action": "confirm",
     "rationale": "<one sentence>"}
  ],
  "proposed": [
    {"title": "<short>", "severity": "<info|low|medium|high|critical>",
     "line": <int or null>, "description": "<2-3 sentences>",
     "rationale": "<one sentence on why this is real>"}
  ]
}
"""

_CROSS_SYSTEM = """You are a smart-contract security auditor specialized in
cross-contract risks: proxy upgrades, delegatecall targets, untrusted callees,
EIP-1967 storage collisions, callback re-entrancy across modules, ERC-777
hooks, interface mismatches, missing checks on returned data from external
calls.

You do TWO things:
  1) Confirm existing findings whose root cause is a cross-contract issue,
     by emitting action="confirm" with a specific rationale.
  2) Propose NEW findings the static engines would not catch.

Respond ONLY as a JSON object, no preamble, no markdown fences:
{
  "decisions": [
    {"id": "<finding id>", "action": "confirm", "rationale": "..."}
  ],
  "proposed": [
    {"title": "<short>", "severity": "<info|low|medium|high|critical>",
     "line": <int or null>, "description": "<2-3 sentences>",
     "rationale": "<one sentence on why this is real>"}
  ]
}
"""


_AGENT_DEFINITIONS = (
    ("severity", _SEVERITY_SYSTEM),
    ("fp", _FP_SYSTEM),
    ("business", _BIZLOGIC_SYSTEM),
    ("cross", _CROSS_SYSTEM),
)


# --- Sub-agent runner --------------------------------------------------------


class _SubAgent:
    """One LLM round-trip with prompt scoped to a single role."""

    def __init__(self, name: str, system_prompt: str, llm: LLMRouter) -> None:
        self.name = name
        self.system_prompt = system_prompt
        self.llm = llm

    async def run(self, *, source: str, findings: list[Finding]) -> AgentReport:
        user = _build_user_prompt(source=source, findings=findings)
        try:
            raw = await self.llm.complete(
                LLMRequest(
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user},
                    ],
                    sensitivity=Sensitivity.HIGH,
                    temperature=0.1,
                    max_tokens=4096,
                )
            )
        except Exception as e:
            logger.warning("multiagent.llm_failed", agent=self.name, error=str(e))
            return AgentReport(agent=self.name, failed=True, error=str(e))

        parsed = _parse_json_envelope(raw)
        if parsed is None:
            logger.warning("multiagent.parse_failed", agent=self.name, head=raw[:200])
            return AgentReport(agent=self.name, failed=True, error="parse failed")

        return _normalize_report(self.name, parsed)


# --- Orchestrator ------------------------------------------------------------


class MultiAgentTriage:
    """Runs four sub-agents in parallel + consensus merge."""

    def __init__(
        self,
        llm: LLMRouter | None = None,
        *,
        max_source_chars: int = 24_000,
        max_findings_in_prompt: int = 40,
    ) -> None:
        self.llm = llm or LLMRouter()
        self.max_source_chars = max_source_chars
        self.max_findings_in_prompt = max_findings_in_prompt

    async def run(
        self, findings: list[Finding], *, source: str
    ) -> list[Finding]:
        triageable = [f for f in findings if self._needs_triage(f)]
        if not triageable and not source.strip():
            return findings

        bounded_source = source[: self.max_source_chars]
        bounded_findings = triageable[: self.max_findings_in_prompt]

        reports: list[AgentReport] = []

        async def _spawn(name: str, system: str) -> None:
            agent = _SubAgent(name=name, system_prompt=system, llm=self.llm)
            reports.append(await agent.run(source=bounded_source, findings=bounded_findings))

        async with anyio.create_task_group() as tg:
            for name, system in _AGENT_DEFINITIONS:
                tg.start_soon(_spawn, name, system)

        return _consensus_merge(originals=findings, reports=reports)

    # --- Internals -----------------------------------------------------------

    def _needs_triage(self, f: Finding) -> bool:
        if f.dismissed:
            return False
        if f.severity == Severity.INFO:
            return False
        return not (f.severity == Severity.LOW and f.confidence >= 0.8)


# --- Prompting helpers -------------------------------------------------------


def _build_user_prompt(*, source: str, findings: list[Finding]) -> str:
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

    return "\n".join([
        "SOURCE CODE:", "```solidity", source, "```", "",
        "RAW FINDINGS:", findings_json,
    ])


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json_envelope(raw: str) -> dict | None:
    """Tolerant JSON parser that strips ``` fences and falls back to a brace search."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.DOTALL)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        m = _JSON_BLOCK.search(cleaned)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _normalize_report(agent: str, payload: dict) -> AgentReport:
    decisions: list[AgentDecision] = []
    proposed: list[ProposedFinding] = []

    for d in payload.get("decisions") or []:
        if not isinstance(d, dict) or not d.get("id"):
            continue
        action = (d.get("action") or "").lower().strip()
        if action not in ("keep", "reclassify", "dismiss", "confirm"):
            continue
        new_sev_raw = (d.get("new_severity") or "").lower().strip()
        new_sev: Severity | None
        try:
            new_sev = Severity(new_sev_raw) if new_sev_raw else None
        except ValueError:
            new_sev = None
        decisions.append(
            AgentDecision(
                finding_id=str(d["id"]),
                action=action,
                new_severity=new_sev,
                rationale=str(d.get("rationale") or "").strip(),
            )
        )

    for p in payload.get("proposed") or []:
        if not isinstance(p, dict):
            continue
        title = str(p.get("title") or "").strip()
        if not title:
            continue
        sev_raw = (p.get("severity") or "medium").lower().strip()
        try:
            sev = Severity(sev_raw)
        except ValueError:
            sev = Severity.MEDIUM
        proposed.append(
            ProposedFinding(
                title=title,
                description=str(p.get("description") or "").strip(),
                severity=sev,
                line=_safe_int(p.get("line")),
                rationale=str(p.get("rationale") or "").strip(),
            )
        )

    return AgentReport(agent=agent, decisions=decisions, proposed=proposed)


def _safe_int(v: object) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# --- Consensus merge ---------------------------------------------------------


def _consensus_merge(
    *, originals: list[Finding], reports: list[AgentReport]
) -> list[Finding]:
    """Merge sub-agent reports into a final findings list.

    Rules:
      1. Severity: SeverityClassifier wins. Business/Cross may BUMP UP by
         one tier if they "confirm" with rationale.
      2. Dismissal: FalsePositiveFilter dismisses iff Severity also says
         low/info OR no other agent confirms.
      3. New findings (from Business/Cross): inserted as fresh findings with
         appropriate engine tag. FP filter cannot dismiss them in same pass.
      4. Confidence: +0.1 per agent that touches the finding (max 1.0).
      5. Agent crashes contribute nothing — no veto effect.
    """
    by_id: dict[str, Finding] = {f.id: f for f in originals}
    out: list[Finding] = list(originals)

    # Build lookup tables from agent reports.
    sev_dec: dict[str, AgentDecision] = {}
    fp_dec: dict[str, AgentDecision] = {}
    confirm_dec: dict[str, list[AgentDecision]] = {}

    for r in reports:
        if r.failed:
            continue
        for d in r.decisions:
            if r.agent == "severity" and d.action in ("keep", "reclassify"):
                sev_dec[d.finding_id] = d
            elif r.agent == "fp" and d.action in ("keep", "dismiss"):
                fp_dec[d.finding_id] = d
            elif r.agent in ("business", "cross") and d.action == "confirm":
                confirm_dec.setdefault(d.finding_id, []).append(d)

    # Update existing findings.
    updated: list[Finding] = []
    for f in out:
        sev = sev_dec.get(f.id)
        fp = fp_dec.get(f.id)
        confirms = confirm_dec.get(f.id, [])

        new_severity = f.severity
        if sev and sev.action == "reclassify" and sev.new_severity is not None:
            new_severity = sev.new_severity

        # Business/Cross can bump up severity by ONE tier if confirmed.
        if confirms:
            new_severity = _bump_one_tier(new_severity)

        dismissed = f.dismissed
        dismissed_reason = f.dismissed_reason

        if fp and fp.action == "dismiss":
            sev_value = sev.new_severity if sev and sev.new_severity else f.severity
            agreement_low = sev_value in (Severity.LOW, Severity.INFO)
            blocked_by_confirm = bool(confirms)
            if agreement_low and not blocked_by_confirm:
                dismissed = True
                dismissed_reason = fp.rationale or "FP filter dismissed"
            elif not blocked_by_confirm:
                # Even without low-severity agreement, FP can dismiss if
                # severity classifier kept severity unchanged (less aggressive)
                if sev is None or sev.action == "keep":
                    dismissed = True
                    dismissed_reason = fp.rationale or "FP filter dismissed"

        touches = sum(1 for x in (sev, fp) if x is not None) + len(confirms)
        new_confidence = min(1.0, f.confidence + 0.1 * touches)

        metadata = dict(f.metadata)
        if sev and sev.rationale:
            metadata["sev_rationale"] = sev.rationale
        if fp and fp.rationale:
            metadata["fp_rationale"] = fp.rationale
        if confirms:
            metadata["confirms"] = [c.rationale for c in confirms if c.rationale]

        updated.append(
            f.model_copy(
                update={
                    "severity": new_severity,
                    "dismissed": dismissed,
                    "dismissed_reason": dismissed_reason,
                    "confidence": new_confidence,
                    "metadata": metadata,
                }
            )
        )

    # Append new findings proposed by business / cross agents.
    proposal_counter: dict[str, int] = {}
    for r in reports:
        if r.failed or r.agent not in ("business", "cross"):
            continue
        engine_tag = f"llm-{r.agent}"
        for p in r.proposed:
            key = f"{engine_tag}:{p.title.lower()}:{p.line or 0}"
            if key in proposal_counter:
                proposal_counter[key] += 1
                continue
            proposal_counter[key] = 1
            updated.append(
                Finding(
                    id=key,
                    title=p.title,
                    description=p.description or p.rationale,
                    severity=p.severity,
                    source_engine=engine_tag,
                    line=p.line,
                    confidence=0.6,
                    metadata={"rationale": p.rationale} if p.rationale else {},
                )
            )

    # Dedupe original-by-id (paranoid)
    seen_ids: set[str] = set()
    deduped: list[Finding] = []
    for f in updated:
        if f.id in seen_ids:
            continue
        seen_ids.add(f.id)
        deduped.append(f)

    # Keep by_id reference for downstream stages (unused but cheap)
    _ = by_id
    return deduped


def _bump_one_tier(s: Severity) -> Severity:
    order = [Severity.INFO, Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
    try:
        idx = order.index(s)
    except ValueError:
        return s
    return order[min(idx + 1, len(order) - 1)]
