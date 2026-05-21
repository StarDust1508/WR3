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

    # ── P1 RULES — Real Solana hack patterns (2022-2026) ───────────────

    # Mango Markets $114M (2022) — remaining_accounts abuse
    _Rule(
        rule_id="remaining-accounts-abuse",
        title="Unchecked remaining_accounts — injection vector",
        severity=Severity.HIGH,
        pattern=re.compile(
            r"\bctx\.remaining_accounts\b",
        ),
        description=(
            "ctx.remaining_accounts provides untyped, unchecked accounts that bypass "
            "Anchor's account validation. An attacker can inject arbitrary accounts "
            "through this vector. The Mango Markets exploit ($114M) used remaining_accounts "
            "to inject fabricated oracle accounts. Always validate: check owner, check "
            "discriminator, bound the length, and verify account keys against expected values."
        ),
        confidence=0.6,
    ),

    # Common Anchor footgun — re-initialization
    _Rule(
        rule_id="init-if-needed-reinit",
        title="init_if_needed allows re-initialization",
        severity=Severity.HIGH,
        pattern=re.compile(
            r"#\[account\([^)]*init_if_needed",
        ),
        description=(
            "#[account(init_if_needed)] will skip initialization if the account already "
            "exists AND has the correct discriminator. But if the account was closed and "
            "re-funded in the same transaction, the discriminator may be zeroed, allowing "
            "re-initialization with attacker-controlled data. Use explicit init + check "
            "for account existence separately."
        ),
        confidence=0.65,
    ),

    # Cetus $223M (May 2025, Sui but same pattern in Rust) — arithmetic overflow
    _Rule(
        rule_id="unsafe-arithmetic-cast",
        title="Unsafe arithmetic cast — potential overflow/truncation",
        severity=Severity.MEDIUM,
        pattern=re.compile(
            r"\bas\s+(?:u8|u16|u32|u64|u128|i8|i16|i32|i64|i128)\b",
        ),
        description=(
            "Rust's `as` keyword performs truncating casts without overflow checks. "
            "In math-heavy code (AMM formulas, price calculations), this can silently "
            "truncate large values, leading to incorrect computations. The Cetus exploit "
            "($223M, 2025) used exactly this: a checked_shl that didn't properly catch "
            "truncation. Use try_from() or checked_* methods instead of `as`."
        ),
        confidence=0.3,
    ),

    # Account reloading — stale cache after CPI
    _Rule(
        rule_id="account-reload-after-cpi",
        title="Account data may be stale after CPI — reload required",
        severity=Severity.MEDIUM,
        pattern=re.compile(
            r"invoke(?:_signed)?\s*\([^)]+\)[^;]*;[^}]{0,500}\.data\.borrow\(\)",
            re.DOTALL,
        ),
        description=(
            "After a CPI (invoke/invoke_signed), the called program may have modified "
            "account data. If this program cached account data before the CPI and reads "
            "the stale cache afterwards, it operates on outdated state. Reload account "
            "data after any CPI that modifies accounts you depend on."
        ),
        confidence=0.4,
    ),

    # ── P2 RULES — Extended Solana/Anchor vulnerability patterns ─────────

    # CRITICAL severity rules

    _Rule(
        rule_id="missing-spl-token-check",
        title="Raw AccountInfo for token account without SPL Token owner verification",
        severity=Severity.CRITICAL,
        pattern=re.compile(
            r"\bAccountInfo[^;]{0,80}(?:unpack_unchecked|unpack_account|unpack\s*\(|try_from_slice|data\.borrow)",
            re.DOTALL,
        ),
        description=(
            "Token account accessed via raw AccountInfo and deserialized manually without "
            "verifying that the account owner is spl_token::ID. An attacker can pass a "
            "fake token account owned by their own program with fabricated balances and "
            "authorities. The Cashio exploit ($48M, 2022) exploited missing token account "
            "validation. Fix: use Anchor's Account<'info, TokenAccount> (which validates "
            "owner automatically) or assert `account.owner == &spl_token::id()` before "
            "deserialization."
        ),
        confidence=0.55,
    ),
    _Rule(
        rule_id="missing-rent-exempt-check",
        title="Account created without rent exemption check",
        severity=Severity.CRITICAL,
        pattern=re.compile(
            r"create_account[^;]{0,1000}(?![\s\S]{0,1000}(?:is_rent_exempt|rent::Rent|Rent::get))",
            re.DOTALL,
        ),
        description=(
            "system_instruction::create_account is called without verifying rent exemption "
            "via Rent::get() / is_rent_exempt(). If the account is not rent-exempt, the "
            "Solana runtime will garbage-collect it after ~2 epochs, causing permanent data "
            "loss and potential denial of service. Fix: calculate minimum lamports with "
            "Rent::get()?.minimum_balance(data_len) and pass that to create_account, or "
            "use Anchor's init constraint which handles rent automatically."
        ),
        confidence=0.45,
    ),
    _Rule(
        rule_id="pda-off-curve-confusion",
        title="create_program_address used instead of find_program_address",
        severity=Severity.CRITICAL,
        pattern=re.compile(
            r"\bcreate_program_address\s*\(",
        ),
        description=(
            "create_program_address does NOT search for a valid off-curve point — it tries "
            "a single bump and fails if the result is on the ed25519 curve. If user-supplied "
            "seeds are used, an attacker can craft seeds that produce an on-curve address, "
            "causing the instruction to fail (DoS) or — worse — producing an address with a "
            "known private key. The Wormhole exploit ($320M, 2022) involved PDA derivation "
            "issues. Fix: always use find_program_address which iterates bumps to guarantee "
            "an off-curve result, and store/verify the canonical bump."
        ),
        confidence=0.6,
    ),

    # HIGH severity rules

    _Rule(
        rule_id="token-2022-hook-reentrancy",
        title="Token-2022 transfer hooks can re-enter the program",
        severity=Severity.HIGH,
        pattern=re.compile(
            r"\b(?:spl_token_2022|token_2022|Token2022)\b",
        ),
        description=(
            "This program uses Token-2022 (SPL Token Extensions). Token-2022 transfer hooks "
            "execute arbitrary code during transfers, creating a reentrancy vector similar to "
            "EVM's ERC-777 callbacks. If program state is modified before issuing a Token-2022 "
            "transfer, the hook can re-enter and observe intermediate state. Fix: follow "
            "checks-effects-interactions pattern — update all state BEFORE issuing the transfer "
            "CPI. Consider using reentrancy guards (mutex flags in account data) for critical "
            "sections."
        ),
        confidence=0.35,
    ),
    _Rule(
        rule_id="missing-freeze-authority-check",
        title="Mint account freeze_authority not verified",
        severity=Severity.HIGH,
        pattern=re.compile(
            r"\bMint<'info>",
        ),
        description=(
            "Mint<'info> is used without verifying freeze_authority. If a protocol accepts "
            "arbitrary mints (e.g., as collateral or LP tokens), an attacker can create a mint "
            "where they control freeze_authority, deposit tokens, then freeze the protocol's "
            "token account — permanently locking funds. This was seen in multiple DeFi rug-pull "
            "patterns. Fix: assert freeze_authority is None or matches a trusted value, or "
            "maintain an allowlist of accepted mints."
        ),
        confidence=0.3,
    ),
    _Rule(
        rule_id="cpi-missing-signer-seeds",
        title="CPI invoke() used where invoke_signed() may be needed for PDA",
        severity=Severity.HIGH,
        pattern=re.compile(
            r"\binvoke\s*\(\s*&(?!.*invoke_signed)",
        ),
        description=(
            "invoke() is called (not invoke_signed) in a context where the program likely "
            "needs to sign as a PDA. If the CPI target expects a PDA-derived signer, invoke() "
            "will fail or — worse — the instruction might succeed with an unintended signer, "
            "leading to unauthorized actions. The Crema Finance exploit ($8.7M, 2022) involved "
            "CPI authority confusion. Fix: use invoke_signed() with the correct PDA seeds "
            "when the program must act as a signer in the CPI call."
        ),
        confidence=0.4,
    ),
    _Rule(
        rule_id="account-data-not-validated-after-deser",
        title="Account deserialized without subsequent data validation",
        severity=Severity.HIGH,
        pattern=re.compile(
            r"(?:try_from_slice|try_deserialize|AnchorDeserialize::deserialize)\s*\([^)]*\)[^;]{0,500}(?!(?:require!|assert!|if\s+.*return\s+Err))",
            re.DOTALL,
        ),
        description=(
            "Account data is deserialized but not validated afterwards. Deserializing raw "
            "bytes only proves the data fits the struct layout — it does NOT prove the data "
            "is semantically valid (e.g., amounts are within range, pubkeys match expected "
            "values, timestamps are not in the past). An attacker can craft accounts with "
            "valid structure but malicious field values. Fix: immediately after deserialization, "
            "use require!() or assert!() to validate all fields that affect program logic."
        ),
        confidence=0.35,
    ),
    _Rule(
        rule_id="missing-close-constraint",
        title="Manual account close without Anchor close constraint",
        severity=Severity.HIGH,
        pattern=re.compile(
            r"\*\*dest\.lamports\.borrow_mut\(\).*\+=.*\*\*source\.lamports\.borrow_mut\(\)",
            re.DOTALL,
        ),
        description=(
            "Account is closed manually by draining lamports instead of using Anchor's "
            "#[account(close = recipient)] constraint. Manual closing is error-prone: "
            "forgetting to zero the account data or clear the discriminator allows a "
            "re-initialization attack in the same transaction (init-after-close). The attacker "
            "re-funds the account before the transaction ends, then re-initializes it with "
            "malicious data. Fix: use #[account(close = recipient)] which handles lamport "
            "transfer, data zeroing, and discriminator clearing atomically."
        ),
        confidence=0.5,
    ),

    # MEDIUM severity rules

    _Rule(
        rule_id="solana-log-injection",
        title="User input passed directly to msg!/sol_log — log injection",
        severity=Severity.MEDIUM,
        pattern=re.compile(
            r"(?:msg!\s*\([^)]*\{[^}]*\}|sol_log\s*\(.*(?:ctx|args|params|input))",
        ),
        description=(
            "User-controlled input is interpolated directly into msg!() or sol_log(). "
            "While Solana logs are not executed, log injection can: (1) confuse off-chain "
            "indexers and monitoring tools that parse logs with regex, (2) inject fake events "
            "that downstream systems interpret as legitimate state changes, (3) exceed compute "
            "budget through large log payloads. The Mango Markets exploit used crafted events "
            "to mislead oracle observers. Fix: sanitize or truncate user input before logging, "
            "and use structured event formats (Anchor events) instead of freeform msg!()."
        ),
        confidence=0.3,
    ),
    _Rule(
        rule_id="large-account-realloc",
        title="Account realloc without proper rent/lamport adjustment",
        severity=Severity.MEDIUM,
        pattern=re.compile(
            r"(?:realloc\s*=|AccountInfo[^;]{0,60}\.realloc\s*\()",
        ),
        description=(
            "Account reallocation (realloc) changes the data size but may not adjust "
            "lamports to maintain rent exemption. If the account grows but lamports are not "
            "increased, the account falls below the rent-exempt threshold and will be "
            "garbage-collected. If the account shrinks, excess lamports remain locked. "
            "Fix: after realloc, recalculate rent with Rent::get()?.minimum_balance(new_len) "
            "and transfer the lamport difference. Anchor's realloc constraint handles this "
            "automatically when paired with realloc::payer and realloc::zero."
        ),
        confidence=0.4,
    ),
    _Rule(
        rule_id="missing-system-program-check",
        title="SystemProgram account not validated — typed as raw AccountInfo",
        severity=Severity.MEDIUM,
        pattern=re.compile(
            r"system_program\s*:\s*AccountInfo",
        ),
        description=(
            "The system_program field is typed as raw AccountInfo instead of "
            "Program<'info, System>. Without type-level validation, an attacker can "
            "substitute a malicious program in place of the real System Program. Any CPI "
            "to this account (create_account, transfer) would then execute arbitrary "
            "attacker code with the program's PDA authority. Fix: type the field as "
            "Program<'info, System> which Anchor validates automatically, or manually "
            "assert system_program.key() == system_program::ID."
        ),
        confidence=0.5,
    ),
    _Rule(
        rule_id="solana-integer-overflow-no-checked",
        title="Arithmetic without checked operations — potential overflow",
        severity=Severity.MEDIUM,
        pattern=re.compile(
            r"(?:\+\s*(?:amount|lamports|balance|price|qty)|(?:amount|lamports|balance|price|qty)\s*\*)",
        ),
        description=(
            "Arithmetic on financial values (amount, lamports, balance, price) uses "
            "standard +/* operators instead of checked_add/checked_mul/checked_sub. "
            "Rust's release mode wraps on overflow silently, potentially allowing an "
            "attacker to cause integer overflow and mint tokens for free or drain funds. "
            "The Cetus exploit ($223M, 2025) exploited unchecked arithmetic in price "
            "calculations. Fix: use .checked_add()/.checked_mul()/.checked_sub() for all "
            "financial math and propagate errors with ok_or(ErrorCode::MathOverflow)?."
        ),
        confidence=0.3,
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
