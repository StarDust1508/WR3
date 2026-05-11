"""Baseline regex/pattern analyzer.

Catches a small but useful set of well-known Solidity bug patterns purely from
the source text — no external binary required. Runs alongside Aderyn/Wake/
Slither and is most useful when those aren't installed yet, or as a fast
sanity-check before heavier engines.

Limitations:
- No AST: regex sees comments and strings, so signal-to-noise is lower.
- We compensate by requiring the pattern AND a near-context check (e.g. for
  unchecked low-level calls we require `.call{...}(` followed by no `require(`
  in the next ~3 lines).

Anything found here is mostly LOW/MEDIUM and LLM triage decides final severity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from audit_engine.analyzers.base import StaticAnalyzer
from audit_engine.types import Finding, Severity


@dataclass(frozen=True)
class Rule:
    rule_id: str
    title: str
    severity: Severity
    swc_id: str | None
    pattern: re.Pattern[str]
    description: str
    confidence: float = 0.5


_RULES: tuple[Rule, ...] = (
    Rule(
        rule_id="tx-origin",
        title="Use of tx.origin for authorization",
        severity=Severity.HIGH,
        swc_id="SWC-115",
        pattern=re.compile(r"\btx\.origin\b"),
        description=(
            "tx.origin can be spoofed via a malicious intermediate contract. "
            "Use msg.sender for authorization instead."
        ),
        confidence=0.75,
    ),
    Rule(
        rule_id="delegatecall-userinput",
        title="delegatecall with potentially user-controlled target",
        severity=Severity.CRITICAL,
        swc_id="SWC-112",
        pattern=re.compile(r"\.delegatecall\s*\("),
        description=(
            "delegatecall executes target bytecode in the caller's storage context. "
            "If the target is user-controlled this is a full takeover. Verify the "
            "target is constant/admin-only and the calldata is sanitized."
        ),
        confidence=0.55,
    ),
    Rule(
        rule_id="block-timestamp-randomness",
        title="block.timestamp / block.number / blockhash used as randomness",
        severity=Severity.MEDIUM,
        swc_id="SWC-120",
        pattern=re.compile(
            r"\b(keccak256|sha256|sha3)\s*\([^)]*\b(block\.timestamp|block\.number|blockhash)\b"
        ),
        description=(
            "Block-level values are predictable by miners and other contracts in the "
            "same block. Do not derive randomness from them; use VRF (Chainlink) or "
            "commit-reveal."
        ),
        confidence=0.7,
    ),
    Rule(
        rule_id="unchecked-low-level-call",
        title="Unchecked low-level call",
        severity=Severity.MEDIUM,
        swc_id="SWC-104",
        # naive: `.call{...}(...)` not followed shortly by `require(success`
        pattern=re.compile(
            r"\.call(?:\{[^}]*\})?\s*\([^)]*\)\s*;",
        ),
        description=(
            "Return value of low-level call is ignored. If the call reverts your "
            "state will be inconsistent. Wrap in require(success, \"...\")."
        ),
        confidence=0.45,
    ),
    Rule(
        rule_id="selfdestruct",
        title="selfdestruct in code path",
        severity=Severity.HIGH,
        swc_id="SWC-106",
        pattern=re.compile(r"\bselfdestruct\s*\(|\bsuicide\s*\("),
        description=(
            "selfdestruct destroys the contract; verify it is gated by hard access "
            "control and that the recipient cannot be hijacked. EIP-4758 deprecates "
            "selfdestruct semantics; modern contracts should not rely on it."
        ),
        confidence=0.6,
    ),
    Rule(
        rule_id="floating-pragma",
        title="Floating pragma version",
        severity=Severity.INFO,
        swc_id="SWC-103",
        pattern=re.compile(r"^\s*pragma\s+solidity\s+[\^~>]", re.MULTILINE),
        description=(
            "Floating pragmas (e.g. ^0.8.0) allow contract to compile with any "
            "matching compiler. Pin to a single audited version for production."
        ),
        confidence=0.85,
    ),
    Rule(
        rule_id="missing-zero-address-check",
        title="Address parameter without zero-address check",
        severity=Severity.LOW,
        swc_id=None,
        pattern=re.compile(
            r"function\s+\w+\s*\([^)]*\baddress\s+(?!0x0)\w+[^)]*\)\s+(?:external|public)",
            re.IGNORECASE,
        ),
        description=(
            "Functions accepting an address parameter from the outside should "
            "verify it is non-zero, otherwise tokens/state can be permanently lost."
        ),
        confidence=0.3,
    ),
)


class BaselineAnalyzer(StaticAnalyzer):
    """Regex-based detector. No external dependencies."""

    name = "baseline"
    cli = "<inproc>"

    async def analyze(self, *, source: str) -> list[Finding]:
        findings: list[Finding] = []
        if not source:
            return findings

        # Strip line/block comments to cut false positives.
        clean = _strip_comments(source)
        line_index = _line_starts(source)

        for rule in _RULES:
            for match in rule.pattern.finditer(clean):
                line_no = _offset_to_line(line_index, match.start())
                findings.append(
                    Finding(
                        id=f"baseline:{rule.rule_id}:{line_no}",
                        title=rule.title,
                        description=rule.description,
                        severity=rule.severity,
                        source_engine=self.name,
                        line=line_no,
                        swc_id=rule.swc_id,
                        confidence=rule.confidence,
                    )
                )
        return findings


_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_COMMENT_LINE = re.compile(r"//[^\n]*")


def _strip_comments(src: str) -> str:
    """Replace comments with whitespace of equal length to preserve offsets."""
    def replace(m: re.Match[str]) -> str:
        return " " * len(m.group(0))

    src = _COMMENT_BLOCK.sub(replace, src)
    src = _COMMENT_LINE.sub(replace, src)
    return src


def _line_starts(src: str) -> list[int]:
    """Return list of offsets where each line begins (1-indexed semantics)."""
    starts = [0]
    for i, ch in enumerate(src):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _offset_to_line(line_starts: list[int], offset: int) -> int:
    # Binary search over the prefix-sorted list of line start offsets.
    lo, hi = 0, len(line_starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if line_starts[mid] <= offset:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1
