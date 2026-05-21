"""LLM-driven invariant generator.

We ask the model to produce a small, focused set of `invariant_*()` functions
specific to the target contract. The point is not to be exhaustive — the
multi-engine pipeline already covers a lot of ground — but to get the
handful of properties a human auditor would write first:

    * sum of user balances equals totalSupply
    * post-state withdrawable amount >= what the user deposited (after fee)
    * price oracle never returns a stale-by-more-than-X value
    * upgrade authority cannot change without a multisig sig
    * ...

The point of having an LLM do this rather than a fixed template is that
generic templates over-constrain (the model knows what `totalSupply` means
for this contract specifically, and what fields its balances live in).
"""

from __future__ import annotations

import json
import re

import structlog

from audit_engine.fuzzing.types import FuzzInvariant
from audit_engine.llm import LLMRequest, LLMRouter, Sensitivity

logger = structlog.get_logger()


_SYSTEM = """You are a smart-contract security engineer. Given a Solidity
contract (and optionally existing findings from static analysis), you propose
a SMALL set (target 3-7) of Foundry-compatible invariants that, if broken
under random sequencing, would indicate a real bug.

Each invariant is a function with prefix `invariant_`, return type bool or
void with `assert(...)`, that holds for ALL well-formed states. Examples:
    function invariant_totalSupplyEqSumBalances() public view {
        // gather sum of tracked accounts ...
        assert(sum == target.totalSupply());
    }

PRIORITY invariant categories (ordered by impact):
  1. BALANCE CONSERVATION: totalSupply == sum(balances), no ETH/token leak,
     withdrawal amount <= deposit amount (after fees).
  2. ACCESS CONTROL: owner/admin state only changeable by authorized roles.
  3. REENTRANCY GUARDS: state consistency between external calls.
  4. PRICE/ORACLE: price within sane bounds, no stale reads.
  5. STATE MACHINE: valid transitions only, no stuck states.

When EXISTING FINDINGS are provided, write invariants that specifically target
those issues. For example, if there's a "reentrancy" finding, write an invariant
that checks balance conservation around that function.

Rules:
  - Only output a JSON object. No prose. No fences.
  - 3 to 7 invariants. Pick the highest-impact ones for THIS contract.
  - Bodies should reference real state visible in the contract source.
  - severity_if_broken: pick the impact if the invariant ever fails.
    Vocabulary: info, low, medium, high, critical.
  - The body should be COMPLETE Solidity — it will be pasted directly inside
    `function invariant_xxx() public { <BODY> }`.

Output:
{
  "invariants": [
    {"name": "invariant_xxx",
     "body": "<solidity body, no signature>",
     "rationale": "<one sentence>",
     "severity_if_broken": "high"}
  ]
}
"""


_USER_TEMPLATE = """TARGET CONTRACT:
```solidity
{source}
```

{findings_section}

Propose 3-7 invariants tailored to this contract. Only the JSON object.
"""


_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)
_VALID_SEVERITY = {"info", "low", "medium", "high", "critical"}


class InvariantGenerator:
    def __init__(
        self,
        llm: LLMRouter | None = None,
        *,
        max_source_chars: int = 48_000,
        max_invariants: int = 7,
    ) -> None:
        self.llm = llm or LLMRouter()
        self.max_source_chars = max_source_chars
        self.max_invariants = max_invariants

    async def generate(
        self,
        *,
        source: str,
        existing_findings: list | None = None,
    ) -> list[FuzzInvariant]:
        if not source.strip():
            return []

        # Build findings section to guide invariant generation.
        findings_section = ""
        if existing_findings:
            lines = ["EXISTING FINDINGS FROM STATIC ANALYSIS (write invariants targeting these):"]
            for f in existing_findings[:15]:
                sev = getattr(f, "severity", None)
                sev_str = sev.value if hasattr(sev, "value") else str(sev)
                title = getattr(f, "title", str(f))
                line = getattr(f, "line", None)
                lines.append(f"  - [{sev_str}] {title} (line {line or '?'})")
            findings_section = "\n".join(lines)

        try:
            raw = await self.llm.complete(
                LLMRequest(
                    messages=[
                        {"role": "system", "content": _SYSTEM},
                        {
                            "role": "user",
                            "content": _USER_TEMPLATE.format(
                                source=source[: self.max_source_chars],
                                findings_section=findings_section,
                            ),
                        },
                    ],
                    sensitivity=Sensitivity.HIGH,
                    temperature=0.2,
                    max_tokens=4000,
                )
            )
        except Exception as e:
            logger.warning("invariant_gen.llm_failed", error=str(e))
            return []

        return self._parse(raw)

    def _parse(self, raw: str) -> list[FuzzInvariant]:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.DOTALL)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            m = _JSON_BLOCK.search(cleaned)
            if not m:
                logger.warning("invariant_gen.parse_failed", head=raw[:200])
                return []
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                return []

        if not isinstance(data, dict):
            return []
        items = data.get("invariants") or []
        if not isinstance(items, list):
            return []

        invariants: list[FuzzInvariant] = []
        seen_names: set[str] = set()
        for item in items[: self.max_invariants]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name.startswith("invariant_") or not _NAME.match(name) or name in seen_names:
                continue
            seen_names.add(name)
            body = str(item.get("body") or "").strip()
            if not body:
                continue
            severity = (item.get("severity_if_broken") or "high").lower().strip()
            if severity not in _VALID_SEVERITY:
                severity = "high"
            invariants.append(
                FuzzInvariant(
                    name=name,
                    body=body,
                    rationale=str(item.get("rationale") or "").strip(),
                    severity_if_broken=severity,  # type: ignore[arg-type]
                )
            )

        return invariants
