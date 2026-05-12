"""Solana / Anchor Sealevel-attacks pattern analyzer.

Distinct from the EVM baseline because:
- Solana programs are Rust, not Solidity. Syntax + idioms differ.
- The bug taxonomy is fundamentally different: account ownership, signer
  checks, PDA derivation, CPI trust, discriminator bypass, etc.

Implementation strategy follows the EVM baseline:
- Strip Rust comments to avoid false positives in documentation
- Regex against the cleaned source
- Each rule maps to one Sealevel-attacks category from
  github.com/coral-xyz/sealevel-attacks (the canonical taxonomy that
  Anchor / Soteria / Sec3 use as a baseline)

Coverage targets:
  1. signer-authorization      — missing Signer / is_signer check
  2. account-ownership         — missing owner check on AccountInfo
  3. arbitrary-cpi             — invoke()/invoke_signed() without program-id check
  4. bump-seed-canonicalization — using user-supplied bump (no find_program_address)
  5. closing-accounts          — manual close without zeroing data + lamports
  6. init-after-close          — re-init seam (no discriminator clear)
  7. duplicate-accounts        — two arg slots that should differ but aren't checked
  8. owner-checks              — public ix doing owner-privileged action without check
  9. pda-sharing               — same PDA seeds across programs (bad multi-program design)
 10. type-cosplay              — bytemuck::from_bytes or unchecked type cast
 11. unsafe-unwrap             — unwrap()/expect() on user-controlled inputs in handlers
 12. unchecked-program-id      — calling external program without verifying its address
 13. floating-pragma-rust      — Cargo `solana-program = "*"` or `^` open-ended

This is signal-to-noise tuned for AI triage downstream: regex catches the
pattern, multi-agent triage (W5) reads context and decides confidence.

Reference: github.com/coral-xyz/sealevel-attacks
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from audit_engine.analyzers.base import StaticAnalyzer
from audit_engine.types import Finding, Severity


@dataclass(frozen=True)
class _Rule:
    rule_id: str
    title: str
    severity: Severity
    pattern: re.Pattern[str]
    description: str
    confidence: float = 0.5


_RULES: tuple[_Rule, ...] = (
    _Rule(
        rule_id="signer-authorization",
        title="Missing signer check on AccountInfo",
        severity=Severity.HIGH,
        # Heuristic: a function takes `&AccountInfo` for an account that
        # likely represents an authority, without an explicit `is_signer`
        # check or Anchor `Signer<'info>` typing.
        pattern=re.compile(
            r"\bAccountInfo<'\w+>\s*,?\s*(?:[^)]{0,200}?\bauth\w*)",
            re.IGNORECASE,
        ),
        description=(
            "Account that appears to act as authority is typed as AccountInfo rather "
            "than Signer<'info>. Anchor will not enforce is_signer. Use Signer<'info> "
            "or assert account.is_signer manually."
        ),
        confidence=0.45,
    ),
    _Rule(
        rule_id="account-ownership-missing",
        title="AccountInfo used without owner check",
        severity=Severity.HIGH,
        # AccountInfo<'info> used in a handler without subsequent ownership
        # assertion in the same function.
        pattern=re.compile(
            r"\bUncheckedAccount<'\w+>",
        ),
        description=(
            "UncheckedAccount skips owner verification. Verify the account is owned "
            "by the expected program before reading its data."
        ),
        confidence=0.6,
    ),
    _Rule(
        rule_id="arbitrary-cpi",
        title="Cross-program invocation without program-id verification",
        severity=Severity.CRITICAL,
        pattern=re.compile(
            r"\binvoke(?:_signed)?\s*\(\s*&?\s*(?:Instruction|ix)\b",
        ),
        description=(
            "invoke()/invoke_signed() called without confirming the destination "
            "program id matches an expected constant. An attacker can pass a "
            "malicious program account and execute arbitrary code with the caller's "
            "PDA authority."
        ),
        confidence=0.55,
    ),
    _Rule(
        rule_id="bump-seed-from-input",
        title="PDA bump seed sourced from caller input",
        severity=Severity.HIGH,
        # The caller-provided bump pattern is `bump = some_arg_from_ix_data` rather
        # than `bump = derived.bump` (computed via find_program_address).
        pattern=re.compile(
            r"\bbump\s*=\s*(?:ctx\.\w+\.|args?\.|params?\.|input\.)",
        ),
        description=(
            "Anchor `bump = ...` constraint reads from caller-supplied input "
            "instead of canonical bump from find_program_address. Attacker can "
            "spoof a non-canonical PDA and bypass authority checks."
        ),
        confidence=0.65,
    ),
    _Rule(
        rule_id="close-without-zero",
        title="Manual account close without data/lamports zeroing",
        severity=Severity.HIGH,
        pattern=re.compile(
            r"\.lamports\s*\(\s*\)\s*\.borrow_mut\s*\(\s*\)\s*\*?\s*=",
        ),
        description=(
            "Manual lamport drain to close an account. To prevent re-init attacks "
            "the discriminator must be cleared and data zeroed. Use Anchor "
            "`close = recipient` constraint or zero the data buffer explicitly."
        ),
        confidence=0.55,
    ),
    _Rule(
        rule_id="duplicate-mutable-accounts",
        title="Two mutable accounts may be the same — no #[account(constraint = a != b)]",
        severity=Severity.MEDIUM,
        # Two Anchor Account<'info, T> args, both mutable, no inter-account constraint.
        pattern=re.compile(
            r"#\[account\(mut\)\][^#]{0,200}#\[account\(mut\)\]",
        ),
        description=(
            "Two #[account(mut)] arguments next to each other without "
            "`constraint = a.key() != b.key()`. If the caller passes the same "
            "account twice the write order can violate accounting invariants."
        ),
        confidence=0.4,
    ),
    _Rule(
        rule_id="unsafe-unwrap",
        title="unwrap()/expect() on caller-controlled input",
        severity=Severity.LOW,
        pattern=re.compile(
            r"(?:ctx\.\w+\.|args?\.|params?\.|input\.|user_\w+\.)[\w.]*\.(?:unwrap|expect)\s*\(",
        ),
        description=(
            "Calling unwrap()/expect() on a value derived from instruction input "
            "panics the transaction. Prefer ok_or() / map_err() with a typed error."
        ),
        confidence=0.5,
    ),
    _Rule(
        rule_id="type-cosplay-bytemuck",
        title="Unchecked bytemuck cast — potential type cosplay",
        severity=Severity.MEDIUM,
        pattern=re.compile(
            # Match the function name; permit turbofish `::<T>` before the call.
            r"\bbytemuck::(?:try_)?from_bytes(?:_mut)?(?:::<[^>]+>)?\s*\(",
        ),
        description=(
            "bytemuck::from_bytes reinterprets raw account data as a struct without "
            "checking the discriminator. Two account types with the same layout become "
            "interchangeable. Use Anchor `Account<'info, T>` which checks the "
            "discriminator, or verify it manually."
        ),
        confidence=0.5,
    ),
    _Rule(
        rule_id="floating-rust-pragma",
        title="Open-ended Solana/Anchor dependency version",
        severity=Severity.INFO,
        pattern=re.compile(
            r'(?:solana-program|anchor-lang)\s*=\s*"[\^~*]',
        ),
        description=(
            "Floating dependency versions for solana-program/anchor-lang let a "
            "future supply-chain compromise pull in malicious code on rebuild. "
            "Pin to exact versions and audit upgrades manually."
        ),
        confidence=0.8,
    ),
    _Rule(
        rule_id="solana-tx-origin-equivalent",
        title="Using accounts[0] as authority (caller-controlled order)",
        severity=Severity.HIGH,
        pattern=re.compile(
            r"\bctx\.accounts\.\w+\.key\s*\(\s*\)\s*==\s*ctx\.accounts\.\w+\.key\s*\(\s*\)",
        ),
        description=(
            "Authority comparison relies on caller-supplied account ordering. "
            "If the underlying account does not include a Signer constraint, the "
            "caller can shuffle accounts to bypass the check."
        ),
        confidence=0.35,
    ),
    _Rule(
        rule_id="cpi-without-allowlist",
        title="invoke_signed to user-supplied program id",
        severity=Severity.CRITICAL,
        pattern=re.compile(
            r"\binvoke_signed\s*\([^)]*ctx\.accounts\.\w+_program",
        ),
        description=(
            "invoke_signed() target program is read directly from a context account "
            "without any allowlist check. Attacker can substitute a malicious program "
            "that abuses the PDA signature."
        ),
        confidence=0.55,
    ),
)


# Strip Rust line and block comments while preserving offsets.
_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_COMMENT_LINE = re.compile(r"//[^\n]*")


def _strip_comments(src: str) -> str:
    def replace(m: re.Match[str]) -> str:
        return " " * len(m.group(0))

    src = _COMMENT_BLOCK.sub(replace, src)
    src = _COMMENT_LINE.sub(replace, src)
    return src


def _line_starts(src: str) -> list[int]:
    starts = [0]
    for i, ch in enumerate(src):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _offset_to_line(line_starts: list[int], offset: int) -> int:
    lo, hi = 0, len(line_starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if line_starts[mid] <= offset:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1


class SolanaSealevelAnalyzer(StaticAnalyzer):
    """Regex-based detector for Solana / Anchor programs. No external deps.

    This is our open-source Solana moat — none of CertiK / Hacken / Olympix /
    Aether ships an open-source Solana static analyzer. Sec3 X-Ray is closed.
    """

    name = "solana-sealevel"
    cli = "<inproc>"

    async def analyze(self, *, source: str) -> list[Finding]:
        findings: list[Finding] = []
        if not source:
            return findings

        clean = _strip_comments(source)
        line_index = _line_starts(source)

        for rule in _RULES:
            for match in rule.pattern.finditer(clean):
                line_no = _offset_to_line(line_index, match.start())
                findings.append(
                    Finding(
                        id=f"solana-sealevel:{rule.rule_id}:{line_no}",
                        title=rule.title,
                        description=rule.description,
                        severity=rule.severity,
                        source_engine=self.name,
                        line=line_no,
                        confidence=rule.confidence,
                    )
                )
        return findings
