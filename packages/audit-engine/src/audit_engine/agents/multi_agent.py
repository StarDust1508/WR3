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

Severity criteria (use these, not gut feelings):
  critical — Direct fund theft/permanent freeze, <$1K attack cost. Examples:
    reentrancy draining ETH, unprotected selfdestruct, delegatecall to
    user-controlled address, unguarded initialize() on proxy.
  high — Conditional fund theft or permanent DoS (requires specific state or
    access). Examples: first-depositor share inflation, oracle manipulation
    with flash loan, missing slippage in AMM swap, broken access control on
    admin functions.
  medium — Potential losses under specific/uncommon conditions, griefing, value
    leakage. Examples: fee-on-transfer token mishandling, division before
    multiplication precision loss, unbounded loops on growing arrays,
    front-runnable timestamp checks.
  low — Minor issues, limited impact, defense-in-depth. Examples: missing
    events, single-step ownership transfer, missing zero-address checks.
  info — Code quality, gas optimization, best practices.

For each finding, decide:
  - keep        — severity guess is correct
  - reclassify  — severity wrong; supply new_severity

IMPORTANT: Err on the side of HIGHER severity, not lower. It is far worse to
under-rate a critical bug than to over-rate a low one. Static analyzers
systematically under-rate business-logic issues. If you see a finding about
reentrancy, unchecked returns, or access control, the correct severity is
usually HIGH or CRITICAL.

Be conservative on dismissal — that is not your job (another agent does FP
filtering). Focus on whether the severity assigned matches the actual impact
visible in the code.

## Few-shot examples

Finding: "Unchecked low-level call" (severity: medium, engine: slither)
Context: The .call{value: amount}("") return is ignored and balances[msg.sender]
  is decremented after the call.
Decision: reclassify → high
Rationale: Unchecked return + state update after call creates reentrancy + silent
  failure — HIGH, not MEDIUM.

Finding: "Use of tx.origin" (severity: medium, engine: baseline)
Context: `require(tx.origin == owner)` in withdraw().
Decision: reclassify → high
Rationale: tx.origin for auth on a fund-moving function enables phishing attacks
  that drain funds — HIGH impact.

Finding: "Floating pragma" (severity: low, engine: aderyn)
Context: `pragma solidity ^0.8.20;`
Decision: reclassify → info
Rationale: Cosmetic compiler hygiene, zero exploit impact.

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
to flag false positives among static-analysis findings.

Severity is irrelevant for you. For each finding, decide:
  - keep    — the finding is real or plausibly real
  - dismiss — the finding is a clear false positive

STRICT RULES for dismissal — you may ONLY dismiss when ALL of:
  1) You can cite a specific code construct (modifier name, require statement,
     function name) that neutralizes the issue.
  2) The mitigation is in the SAME function or a direct caller.
  3) The finding is NOT about reentrancy, access control, or fund movement
     (these are too dangerous to auto-dismiss).

NEVER dismiss:
  - Findings about reentrancy (SWC-107) unless a ReentrancyGuard/nonReentrant
    modifier is literally present on that function.
  - Findings about missing return-value checks on external calls.
  - Findings where the "mitigation" is just a comment or a TODO.
  - Findings on onlyOwner functions — owner compromise is a valid threat model.
  - Findings from the "llm-business-logic" or "llm-cross-contract" engines.

ALWAYS dismiss:
  - Floating pragma / compiler version findings (informational noise).
  - Naming convention / style issues.
  - Findings in test files (paths containing /test/, /mock/, /script/).

## Few-shot examples

Finding: "Unchecked low-level call" on line 42
Code at line 42: `(bool ok,) = recipient.call{value: amount}("");`
Code at line 43: `require(ok, "transfer failed");`
Decision: dismiss
Rationale: Return value is checked via require(ok) on line 43.

Finding: "delegatecall with user-controlled target" on line 80
Code: `implementation.delegatecall(data)` where implementation = storage variable
  set in constructor by deployer.
Decision: keep
Rationale: Although set in constructor, implementation could be changed via upgrade;
  delegatecall to storage variable is dangerous enough to keep flagged.

Finding: "Use of tx.origin" on line 15
Code: `require(tx.origin == msg.sender)` in a view function.
Decision: dismiss
Rationale: tx.origin == msg.sender is a common EOA-only check, not an auth gate.

Respond ONLY as a JSON object, no preamble, no markdown fences:
{
  "decisions": [
    {"id": "<finding id>", "action": "keep" | "dismiss",
     "rationale": "<one sentence with code reference>"}
  ]
}
"""

_BIZLOGIC_SYSTEM = """You are a senior smart-contract security auditor specialized
in business-logic flaws — bugs that regex and AST pattern-matchers CANNOT catch.

Your expertise covers these specific vulnerability classes:
  1. ACCOUNTING ERRORS: balance tracking drift, rounding exploitation,
     first-depositor share inflation (vault deposit 1 wei attack), fee
     calculation bypasses, double-counting, off-by-one in reward distribution.
  2. ORACLE MANIPULATION: stale price feeds, TWAP with short window,
     flash-loan-manipulable spot prices, missing circuit breakers,
     Chainlink sequencer-down check missing on L2.
  3. MEV / FRONT-RUNNING: sandwich-vulnerable swaps, missing slippage,
     front-runnable liquidations, commit-reveal violations, token approval
     race conditions, deadline=block.timestamp (always passes).
  4. ACCESS CONTROL LOGIC: privilege escalation via multi-step calls,
     missing timelocks on critical setters, unprotected initializers,
     role-based access gaps.
  5. TOKEN INTEGRATION: fee-on-transfer mishandling, rebasing token
     incompatibility, ERC-777 callback hooks, missing approve(0) before
     approve(N), non-standard decimals/return values.
  6. STATE MACHINE: invalid state transitions, missing pausability,
     reentrancy through state, cross-function reentrancy.

You do TWO things:
  1) Confirm existing findings whose root cause is a business-logic flaw,
     by emitting action="confirm" with a specific rationale citing code lines.
  2) Propose NEW findings that the static engines would not catch.
     Be SPECIFIC: reference actual function names, state variables, and line
     numbers from the source. Generic observations are useless.

QUALITY BAR for proposed findings:
  - Must reference a concrete function/variable in the source.
  - Must describe a specific attack path or broken invariant.
  - "Might be vulnerable" without a concrete scenario = do not propose.
  - If the contract is a simple ERC-20 with no custom logic, say so and
    propose fewer (or zero) new findings.

## Few-shot examples

Source contains: `function deposit(uint amount) external { shares = amount * totalShares / totalAssets; }`
Proposed finding:
  title: "First depositor share inflation attack"
  severity: critical
  line: 45
  description: "When totalShares=0, first depositor can deposit 1 wei, then
    donate tokens directly to inflate totalAssets. Subsequent depositors get
    0 shares due to rounding. Attacker redeems all deposited funds."
  rationale: "Classic vault inflation — division rounds to 0 for victims."

Source contains: `require(block.timestamp <= deadline)` in swap function
Proposed finding:
  title: "Ineffective swap deadline — always passes"
  severity: medium
  line: 112
  description: "If deadline is set to block.timestamp by the caller, the check
    always passes. A pending transaction can be included at any future block.
    The deadline should be set to a specific future timestamp by the user."
  rationale: "block.timestamp == deadline is trivially satisfiable by miners."

Respond ONLY as a JSON object, no preamble, no markdown fences:
{
  "decisions": [
    {"id": "<finding id>", "action": "confirm",
     "rationale": "<one sentence citing code>"}
  ],
  "proposed": [
    {"title": "<short>", "severity": "<info|low|medium|high|critical>",
     "line": <int or null>, "description": "<2-3 sentences with concrete attack path>",
     "rationale": "<one sentence on why this is real>"}
  ]
}
"""

_CROSS_SYSTEM = """You are a senior smart-contract security auditor specialized in
cross-contract and inter-module risks.

Your expertise covers these specific vulnerability classes:
  1. PROXY PATTERNS: uninitialized proxy implementations, storage collisions
     between proxy and impl, UUPS missing _authorizeUpgrade access control,
     transparent proxy selector clashing, implementation slot hijacking.
  2. DELEGATECALL: delegatecall to untrusted/upgradeable target, storage layout
     mismatch, context confusion (msg.sender/msg.value preservation).
  3. EXTERNAL CALL SAFETY: unchecked return values, reentrancy via callbacks
     (ERC-721 onERC721Received, ERC-777 tokensReceived, flash loan callbacks),
     call to potentially destructed contract, gas griefing with returndatasize.
  4. INTERFACE MISMATCHES: calling a function that doesn't exist on target
     (silent success with empty returndata), wrong selector, ABI encoding
     incompatibility, non-standard ERC-20 implementations.
  5. TRUST BOUNDARIES: hardcoded trusted addresses that can be upgraded,
     over-permissive approve/allowances, missing validation on callback data,
     cross-chain bridge message validation.

You do TWO things:
  1) Confirm existing findings whose root cause is a cross-contract issue,
     by emitting action="confirm" with a specific rationale citing code lines.
  2) Propose NEW findings the static engines would not catch.

QUALITY BAR for proposed findings:
  - Must identify TWO specific contracts/interfaces involved.
  - Must describe the concrete trust violation or data flow issue.
  - "Could be dangerous" without naming the specific interaction = do not propose.

## Few-shot examples

Source contains: `function _authorizeUpgrade(address) internal override {}`
Proposed finding:
  title: "UUPS upgrade without access control"
  severity: critical
  line: 200
  description: "_authorizeUpgrade has an empty body — anyone can upgrade the
    implementation to a malicious contract and drain all funds."
  rationale: "Missing onlyOwner/onlyRole in UUPS upgrade gate."

Source contains: `IERC20(token).transfer(to, amount);`
Proposed finding:
  title: "Unchecked ERC-20 transfer — non-reverting tokens silently fail"
  severity: medium
  line: 88
  description: "USDT, BNB, and other tokens return false instead of reverting
    on failed transfer. Without checking the return value, the contract
    assumes the transfer succeeded and updates state accordingly."
  rationale: "IERC20.transfer return value not checked — SafeERC20 needed."

Respond ONLY as a JSON object, no preamble, no markdown fences:
{
  "decisions": [
    {"id": "<finding id>", "action": "confirm", "rationale": "..."}
  ],
  "proposed": [
    {"title": "<short>", "severity": "<info|low|medium|high|critical>",
     "line": <int or null>, "description": "<2-3 sentences with concrete interaction path>",
     "rationale": "<one sentence on why this is real>"}
  ]
}
"""


# Trivial code-style patterns that info-severity findings can match.
# Title substrings are matched case-insensitively.
_TRIVIAL_INFO_PATTERNS: tuple[str, ...] = (
    "floating pragma",
    "pragma solidity",
    "push0",
    "indexed field",
    "indexed param",
    "events not indexed",
    "missing indexed",
    "solc version",
    "compiler version",
    "naming convention",
    "unused import",
    "immutable-states",
    "immutable state",
    "constable-states",
    "low-level-calls",
    "low level call",
    "assembly",
    "solidity naming",
    "different-pragma",
    "dead-code",
    "cache array length",
    "boolean equality",
    "empty block",
    "redundant statement",
)

_TRIVIAL_LOW_PATTERNS: tuple[str, ...] = (
    "push0",
    "empty require",
    "empty revert",
    "missing zero-check",
    "missing zero-address",
    "zero address",
    "floating rust pragma",
    "solidity pragma should be specific",
    "erc-4337",
)


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
        max_source_chars: int = 48_000,
        max_findings_in_prompt: int = 40,
    ) -> None:
        self.llm = llm or LLMRouter()
        self.max_source_chars = max_source_chars
        self.max_findings_in_prompt = max_findings_in_prompt

    async def run(
        self, findings: list[Finding], *, source: str
    ) -> list[Finding]:
        # Pre-filter: auto-dismiss trivial info findings before LLM calls.
        findings = _auto_dismiss_trivial(findings)

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
        # Everything non-dismissed enters triage. Even LOW findings need
        # FP filtering, and the severity classifier may upgrade them.
        return True


# --- Pre-filter for trivial findings -----------------------------------------


def _auto_dismiss_trivial(findings: list[Finding]) -> list[Finding]:
    """Auto-dismiss findings whose title matches known trivial patterns.

    INFO severity: matches _TRIVIAL_INFO_PATTERNS.
    LOW severity: matches _TRIVIAL_LOW_PATTERNS (stricter subset).
    """
    out: list[Finding] = []
    for f in findings:
        if f.dismissed:
            out.append(f)
            continue
        title_lower = f.title.lower()
        if f.severity == Severity.INFO and any(
            pat in title_lower for pat in _TRIVIAL_INFO_PATTERNS
        ):
            out.append(
                f.model_copy(
                    update={
                        "dismissed": True,
                        "dismissed_reason": "trivial code style issue",
                    }
                )
            )
        elif f.severity == Severity.LOW and any(
            pat in title_lower for pat in _TRIVIAL_LOW_PATTERNS
        ):
            out.append(
                f.model_copy(
                    update={
                        "dismissed": True,
                        "dismissed_reason": "low-impact cosmetic issue",
                    }
                )
            )
        else:
            out.append(f)
    return out


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
                "description": f.description[:1200],
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
        # IMPORTANT: metadata must be initialized BEFORE the FP-dismiss block
        # which may write to it (fp_flagged_but_kept for HIGH/CRITICAL).
        metadata = dict(f.metadata)

        if fp and fp.action == "dismiss":
            effective_sev = new_severity  # after reclassification
            blocked_by_confirm = bool(confirms)
            # HIGH/CRITICAL findings CANNOT be dismissed by FP filter alone.
            # This prevents the most dangerous class of false-negative:
            # a real HIGH/CRIT bug auto-dismissed because the FP filter
            # doesn't understand the full context.
            is_dangerous = effective_sev in (Severity.HIGH, Severity.CRITICAL)

            if blocked_by_confirm:
                # Business/Cross agent explicitly confirmed — never dismiss.
                pass
            elif is_dangerous:
                # HIGH/CRITICAL: FP filter cannot dismiss. At best, add a
                # metadata note that FP filter flagged it.
                metadata["fp_flagged_but_kept"] = fp.rationale or "FP filter wanted dismiss"
            elif effective_sev in (Severity.LOW, Severity.INFO):
                # LOW/INFO: FP filter can dismiss freely.
                dismissed = True
                dismissed_reason = fp.rationale or "FP filter dismissed"
            elif f.confidence < 0.4:
                # MEDIUM with very low confidence: FP can dismiss.
                dismissed = True
                dismissed_reason = fp.rationale or "FP filter dismissed (low confidence)"
            else:
                # MEDIUM with decent confidence: only dismiss if severity
                # classifier also agrees it's low-impact (didn't upgrade).
                if sev and sev.action == "keep" and f.severity == Severity.MEDIUM:
                    dismissed = True
                    dismissed_reason = fp.rationale or "FP filter dismissed"

        touches = sum(1 for x in (sev, fp) if x is not None) + len(confirms)
        new_confidence = min(1.0, f.confidence + 0.1 * touches)
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
