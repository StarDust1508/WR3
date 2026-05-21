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
    # ── CRITICAL ────────────────────────────────────────────────────────
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
        rule_id="unprotected-initializer",
        title="Unprotected initializer function",
        severity=Severity.CRITICAL,
        swc_id=None,
        pattern=re.compile(
            r"function\s+initialize\s*\([^)]*\)\s+(?:external|public)\b(?!.*\binitializer\b)",
            re.DOTALL,
        ),
        description=(
            "Public initialize() without OpenZeppelin's `initializer` modifier can be "
            "front-run or called multiple times, allowing an attacker to hijack proxy "
            "ownership or re-set critical state."
        ),
        confidence=0.7,
    ),
    Rule(
        rule_id="unprotected-selfdestruct",
        title="selfdestruct in code path",
        severity=Severity.CRITICAL,
        swc_id="SWC-106",
        pattern=re.compile(r"\bselfdestruct\s*\(|\bsuicide\s*\("),
        description=(
            "selfdestruct destroys the contract and sends all ETH to the recipient. "
            "Verify it is gated by strong access control (onlyOwner + timelock). "
            "EIP-4758 deprecates selfdestruct semantics on post-Cancun chains."
        ),
        confidence=0.6,
    ),

    # ── HIGH ────────────────────────────────────────────────────────────
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
        rule_id="reentrancy-external-call-before-state",
        title="Potential reentrancy: external call before state update",
        severity=Severity.HIGH,
        swc_id="SWC-107",
        pattern=re.compile(
            r"\.call\{[^}]*value\s*:[^}]*\}\s*\([^)]*\)[^;]*;[^}]{0,300}"
            r"(balances?\s*\[|_balances?\s*\[|\.balance\s*[-+]|mapping.*-=|mapping.*\+=)",
            re.DOTALL,
        ),
        description=(
            "External ETH transfer via .call{value:...}() appears before a state "
            "variable update (balance decrement). This is the classic reentrancy "
            "pattern. Apply checks-effects-interactions or use ReentrancyGuard."
        ),
        confidence=0.65,
    ),
    Rule(
        rule_id="reentrancy-erc721-callback",
        title="ERC-721/ERC-1155 callback reentrancy risk",
        severity=Severity.HIGH,
        swc_id="SWC-107",
        pattern=re.compile(
            r"\b(safeTransferFrom|safeMint|_safeMint|_safeTransfer|safeTransfer)\b"
        ),
        description=(
            "Safe transfer functions call onERC721Received/onERC1155Received on the "
            "recipient, which can re-enter the contract. Ensure state is fully updated "
            "before the transfer, or use ReentrancyGuard."
        ),
        confidence=0.4,
    ),
    Rule(
        rule_id="ecrecover-no-zero-check",
        title="ecrecover without zero-address check",
        severity=Severity.HIGH,
        swc_id="SWC-117",
        pattern=re.compile(r"\becrecover\s*\("),
        description=(
            "ecrecover returns address(0) on invalid signatures instead of reverting. "
            "Without checking `recovered != address(0)`, an attacker with a malleable "
            "signature can impersonate the zero address or bypass permit checks."
        ),
        confidence=0.7,
    ),
    Rule(
        rule_id="arbitrary-external-call",
        title="Arbitrary external call with user-controlled target",
        severity=Severity.HIGH,
        swc_id=None,
        pattern=re.compile(
            r"(?:address\s*\([^)]*\)|[a-zA-Z_]\w*)\s*\.\s*call\{[^}]*\}\s*\(\s*[a-zA-Z_]"
        ),
        description=(
            "Low-level .call{} to an address that may be user-controlled enables "
            "arbitrary code execution in the callee's context, potentially draining "
            "funds from this contract."
        ),
        confidence=0.45,
    ),
    Rule(
        rule_id="unsafe-ownership-transfer",
        title="Single-step ownership transfer without confirmation",
        severity=Severity.HIGH,
        swc_id=None,
        pattern=re.compile(
            r"function\s+transferOwnership\s*\([^)]*\)\s+(?:external|public)\b"
        ),
        description=(
            "Single-step ownership transfer risks permanent lockout if the new owner "
            "address is wrong. Use Ownable2Step (two-step transfer with acceptOwnership) "
            "to prevent irreversible mistakes."
        ),
        confidence=0.5,
    ),

    # ── MEDIUM ──────────────────────────────────────────────────────────
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
        title="Unchecked low-level call return value",
        severity=Severity.MEDIUM,
        swc_id="SWC-104",
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
        rule_id="approve-race-condition",
        title="ERC-20 approve() front-running race condition",
        severity=Severity.MEDIUM,
        swc_id=None,
        pattern=re.compile(
            r"function\s+approve\s*\(\s*address\s+\w+\s*,\s*uint256\s+\w+\s*\)",
        ),
        description=(
            "The standard ERC-20 approve() is vulnerable to a front-running race "
            "condition. If the owner changes the allowance from N to M, the spender "
            "can front-run and spend N+M. Use increaseAllowance/decreaseAllowance "
            "or SafeERC20."
        ),
        confidence=0.35,
    ),
    Rule(
        rule_id="missing-slippage-protection",
        title="Swap/exchange without slippage protection",
        severity=Severity.MEDIUM,
        swc_id=None,
        pattern=re.compile(
            r"\b(swapExact|swap|exchange)\w*\s*\([^)]*(?:0\s*(?:,|\))|amountOutMin\s*=?\s*0)",
        ),
        description=(
            "Swap function called with zero or missing minimum output amount, making "
            "the transaction vulnerable to sandwich attacks and MEV extraction. Always "
            "enforce a user-specified amountOutMin."
        ),
        confidence=0.5,
    ),
    Rule(
        rule_id="unchecked-erc20-transfer",
        title="Unchecked ERC-20 transfer/transferFrom return value",
        severity=Severity.MEDIUM,
        swc_id=None,
        pattern=re.compile(
            r"\.\s*(?:transfer|transferFrom)\s*\([^)]+\)\s*;",
        ),
        description=(
            "ERC-20 transfer/transferFrom may return false on failure instead of "
            "reverting (USDT, BNB, etc.). Not checking the return value means "
            "the contract will proceed as if the transfer succeeded. Use "
            "SafeERC20.safeTransfer."
        ),
        confidence=0.5,
    ),
    Rule(
        rule_id="timestamp-dependence",
        title="Timestamp dependence in conditional logic",
        severity=Severity.MEDIUM,
        swc_id="SWC-116",
        pattern=re.compile(
            r"\b(block\.timestamp|now)\s*(>|<|>=|<=|==|!=)\s*"
        ),
        description=(
            "block.timestamp can be manipulated by miners within ~15 seconds. "
            "If the condition controls fund release, locking, or auction timing, "
            "an attacker-miner can manipulate the outcome."
        ),
        confidence=0.4,
    ),
    Rule(
        rule_id="unbounded-loop",
        title="Unbounded loop over dynamic array — potential DoS",
        severity=Severity.MEDIUM,
        swc_id="SWC-128",
        pattern=re.compile(
            r"for\s*\(\s*(?:uint\d*\s+)?\w+\s*=\s*0\s*;\s*\w+\s*<\s*\w+\.length\s*;",
        ),
        description=(
            "Loop iterating over a dynamic-length storage array can exceed the block "
            "gas limit as the array grows, causing permanent DoS. Use pagination or "
            "bounded iterations."
        ),
        confidence=0.45,
    ),
    Rule(
        rule_id="division-before-multiplication",
        title="Division before multiplication — precision loss",
        severity=Severity.MEDIUM,
        swc_id=None,
        pattern=re.compile(
            r"\b\w+\s*/\s*\w+\s*\*\s*\w+\b",
        ),
        description=(
            "Solidity integer division truncates. Dividing before multiplying loses "
            "precision and can silently undercount fees, rewards, or shares. "
            "Rearrange: multiply first, then divide."
        ),
        confidence=0.35,
    ),
    Rule(
        rule_id="fee-on-transfer-token",
        title="Token amount assumed exact after transfer",
        severity=Severity.MEDIUM,
        swc_id=None,
        pattern=re.compile(
            r"transferFrom\s*\([^)]+\)\s*;[^}]{0,200}(amount|_amount|value)\b",
            re.DOTALL,
        ),
        description=(
            "The actual received amount may differ from the requested amount for "
            "fee-on-transfer or rebasing tokens. Measure balance before/after "
            "the transfer instead of trusting the input amount."
        ),
        confidence=0.4,
    ),
    Rule(
        rule_id="hardcoded-gas-amount",
        title="Hardcoded gas amount in external call",
        severity=Severity.MEDIUM,
        swc_id=None,
        pattern=re.compile(r"\.call\{\s*gas\s*:\s*\d+"),
        description=(
            "Hardcoded gas amounts break when opcode costs change (e.g. EIP-1884, "
            "EIP-2929). The callee may receive insufficient gas, causing silent "
            "failures. Forward all gas unless there's a specific reentrancy reason."
        ),
        confidence=0.55,
    ),
    Rule(
        rule_id="storage-collision-proxy",
        title="Potential storage collision in proxy pattern",
        severity=Severity.MEDIUM,
        swc_id=None,
        pattern=re.compile(
            r"\bsload\s*\(\s*0x[0-9a-fA-F]+\s*\)|"
            r"\bsstore\s*\(\s*0x[0-9a-fA-F]+\s*,",
        ),
        description=(
            "Direct sload/sstore at a fixed slot can collide with storage variables "
            "inherited from proxy or implementation contracts. Use EIP-1967 standard "
            "slots or diamond storage to avoid unpredictable overwrites."
        ),
        confidence=0.5,
    ),

    # ── LOW ─────────────────────────────────────────────────────────────
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
    Rule(
        rule_id="missing-event-emission",
        title="State change without event emission",
        severity=Severity.LOW,
        swc_id=None,
        pattern=re.compile(
            r"function\s+set\w+\s*\([^)]*\)\s+(?:external|public)[^}]{10,300}"
            r"(?:=\s*\w+\s*;)(?!.*emit\s)",
            re.DOTALL,
        ),
        description=(
            "Public setter modifies state but does not emit an event. Off-chain "
            "monitoring and indexers depend on events to detect critical parameter "
            "changes."
        ),
        confidence=0.35,
    ),

    # ── P1 RULES — Real hack patterns (2023-2026) ──────────────────────

    # Euler Finance $197M, BonqDAO $120M, Harvest $34M pattern
    Rule(
        rule_id="oracle-spot-price-dependency",
        title="Spot price used as oracle — flash loan manipulable",
        severity=Severity.HIGH,
        swc_id=None,
        pattern=re.compile(
            r"\b(getReserves|slot0|balanceOf\s*\(\s*address\s*\(\s*this\s*\))\s*\(",
        ),
        description=(
            "Using DEX spot prices (getReserves, slot0) or contract's own balance "
            "(balanceOf(address(this))) as a price oracle is manipulable via flash "
            "loans. An attacker can borrow a large amount, skew the price, interact "
            "with this contract at the distorted price, then repay. Use Chainlink "
            "TWAP or time-weighted averages."
        ),
        confidence=0.5,
    ),

    # Chainlink staleness — Mango $114M + dozens of lending forks
    Rule(
        rule_id="chainlink-stale-price",
        title="Chainlink latestRoundData without staleness check",
        severity=Severity.HIGH,
        swc_id=None,
        pattern=re.compile(
            r"latestRoundData\s*\(\s*\)",
        ),
        description=(
            "Chainlink's latestRoundData() can return stale prices if the feed is "
            "paused or the oracle is down. Without checking `updatedAt` or "
            "`answeredInRound >= roundId`, the contract may use an outdated price "
            "for critical operations (liquidations, borrows, swaps). Add: "
            "require(block.timestamp - updatedAt < STALENESS_THRESHOLD)."
        ),
        confidence=0.55,
    ),

    # ERC-4626 inflation — sfrxETH + many vault forks
    Rule(
        rule_id="erc4626-inflation-attack",
        title="ERC-4626 vault without inflation protection",
        severity=Severity.CRITICAL,
        swc_id=None,
        pattern=re.compile(
            r"function\s+deposit\s*\([^)]*\)[^}]{0,500}totalAssets\s*\(\s*\)",
            re.DOTALL,
        ),
        description=(
            "ERC-4626 vaults computing shares as `assets * totalSupply / totalAssets` "
            "are vulnerable to inflation attacks. First depositor deposits 1 wei, then "
            "donates a large amount directly to inflate totalAssets. Subsequent depositors "
            "get 0 shares due to rounding. Mitigation: use virtual shares/assets offset "
            "(OpenZeppelin 4.9+) or mint dead shares on first deposit."
        ),
        confidence=0.45,
    ),

    # Missing deadline in swap — MEV sandwich vector
    Rule(
        rule_id="swap-missing-deadline",
        title="Swap without deadline parameter — MEV vulnerable",
        severity=Severity.MEDIUM,
        swc_id=None,
        pattern=re.compile(
            r"\b(swap|exactInput|exactOutput|swapExact)\w*\s*\([^)]*"
            r"(?:deadline\s*:\s*block\.timestamp|deadline\s*=\s*block\.timestamp)",
        ),
        description=(
            "Setting swap deadline to block.timestamp makes it always pass — the "
            "transaction can sit in the mempool indefinitely and be executed at any "
            "future block. This allows sandwich attacks and stale-price exploitation. "
            "Deadline should be a specific future timestamp set by the caller."
        ),
        confidence=0.6,
    ),

    # Unprotected _disableInitializers — proxy implementation takeover
    Rule(
        rule_id="implementation-without-disable-initializers",
        title="Upgradeable implementation without _disableInitializers()",
        severity=Severity.CRITICAL,
        swc_id=None,
        pattern=re.compile(
            r"contract\s+\w+\s+is\s+[^{]*(?:Initializable|UUPSUpgradeable|"
            r"TransparentUpgradeableProxy)[^{]*\{"
            r"(?![\s\S]{0,500}_disableInitializers\s*\(\s*\))",
            re.DOTALL,
        ),
        description=(
            "Upgradeable implementation contract inherits Initializable but its "
            "constructor does not call _disableInitializers(). An attacker can call "
            "initialize() directly on the implementation (not via proxy), potentially "
            "taking ownership and then self-destructing it, bricking the proxy."
        ),
        confidence=0.5,
    ),

    # Unprotected UUPS upgrade — critical access control
    Rule(
        rule_id="uups-unprotected-upgrade",
        title="UUPS _authorizeUpgrade without access control",
        severity=Severity.CRITICAL,
        swc_id=None,
        pattern=re.compile(
            r"function\s+_authorizeUpgrade\s*\([^)]*\)\s+"
            r"(?:internal|public|external)\s+(?:virtual\s+)?override\s*\{"
            r"\s*\}",
            re.DOTALL,
        ),
        description=(
            "_authorizeUpgrade() has an empty body — anyone can upgrade the "
            "implementation to a malicious contract and drain all funds. "
            "Add onlyOwner or onlyRole modifier."
        ),
        confidence=0.85,
    ),

    # Flash loan callback present — informational signal for LLM
    Rule(
        rule_id="flash-loan-callback",
        title="Flash loan callback detected — verify interaction safety",
        severity=Severity.MEDIUM,
        swc_id=None,
        pattern=re.compile(
            r"function\s+(onFlashLoan|executeOperation|receiveFlashLoan|"
            r"uniswapV[23]FlashCallback|pancakeV3FlashCallback)\s*\(",
        ),
        description=(
            "This contract implements a flash loan callback, indicating it "
            "interacts with flash-loan-capable protocols. Verify: (1) the callback "
            "validates msg.sender is the expected pool/lender, (2) no re-entrancy "
            "via the callback, (3) the repayment logic cannot be manipulated."
        ),
        confidence=0.4,
    ),

    # ── P2 RULES — Advanced EVM patterns (2023-2026) ──────────────────

    # CRITICAL — Read-only reentrancy (Curve/Euler hacks)
    Rule(
        rule_id="read-only-reentrancy",
        title="Read-only reentrancy — view function reads manipulable state",
        severity=Severity.CRITICAL,
        swc_id="SWC-107",
        pattern=re.compile(
            r"function\s+\w+\s*\([^)]*\)\s+(?:external|public)\s+view\s+returns\s*\("
            r"[^)]*\)[^}]{0,500}"
            r"(?:totalSupply|totalAssets|getReserves|balanceOf\s*\(\s*address\s*\(\s*this\s*\)\s*\))",
            re.DOTALL,
        ),
        description=(
            "View function reads state (totalSupply, totalAssets, getReserves, "
            "balanceOf(address(this))) that can be stale during a callback from an "
            "external call in another function. An attacker can exploit this by "
            "re-entering the view function mid-transaction while state is inconsistent "
            "(e.g. Curve reentrancy 2023, Euler $197M hack). Mitigation: apply "
            "ReentrancyGuard to view functions that read shared state, or use "
            "reentrancy locks that also cover read paths."
        ),
        confidence=0.4,
    ),

    # CRITICAL — returndata bomb
    Rule(
        rule_id="returndata-bomb",
        title="returndatacopy without bounds check — returndata bomb",
        severity=Severity.CRITICAL,
        swc_id=None,
        pattern=re.compile(r"\breturndatacopy\b"),
        description=(
            "Assembly block uses returndatacopy without validating returndatasize(). "
            "A malicious callee can return an extremely large payload, causing the "
            "caller to run out of gas when copying return data into memory. Verify "
            "returndatasize() is bounded before copying, or use a fixed-size buffer."
        ),
        confidence=0.5,
    ),

    # HIGH — Signature replay without nonce
    Rule(
        rule_id="signature-replay-no-nonce",
        title="Signature verification without nonce — replay attack",
        severity=Severity.HIGH,
        swc_id="SWC-121",
        pattern=re.compile(
            r"(?:ecrecover|ECDSA\.recover|SignatureChecker)\s*\("
            r"(?![\s\S]{0,500}nonce)",
            re.DOTALL,
        ),
        description=(
            "ecrecover/ECDSA.recover is used without apparent nonce tracking. Without "
            "incrementing a nonce per-signer, the same signature can be replayed to "
            "execute the action multiple times. Include a nonce in the signed message "
            "and increment it on each use (see EIP-712 + nonce pattern)."
        ),
        confidence=0.45,
    ),

    # HIGH — Permit drain
    Rule(
        rule_id="permit-drain-erc20",
        title="ERC-20 with permit() — potential permit-drain vector",
        severity=Severity.HIGH,
        swc_id=None,
        pattern=re.compile(
            r"function\s+permit\s*\([^)]*\)[^}]*}"
            r"[\s\S]*"
            r"function\s+transferFrom\s*\(",
            re.DOTALL,
        ),
        description=(
            "Token implements both permit() and transferFrom(). If transferFrom does "
            "not properly validate allowance, an attacker can use gasless permit "
            "signatures to approve themselves and drain tokens in one transaction. "
            "Verify that transferFrom correctly decrements allowance and that permit "
            "follows EIP-2612 exactly. Real-world impact: multiple permit-drain "
            "exploits on non-standard ERC-20 implementations."
        ),
        confidence=0.3,
    ),

    # HIGH — Governance flash loan
    Rule(
        rule_id="governance-flash-loan",
        title="Voting power based on current balance — flash-loan governance",
        severity=Severity.HIGH,
        swc_id=None,
        pattern=re.compile(
            r"(?:balanceOf[^;]*vot|voting[^;]*balanceOf|getVotes[^;]*balanceOf)",
            re.IGNORECASE,
        ),
        description=(
            "Voting power appears to be derived from current token balance rather than "
            "a historical snapshot. An attacker can flash-loan tokens, vote or propose, "
            "then return them in the same transaction. Use ERC20Votes with checkpoints "
            "or ERC20Snapshot to base voting power on a past block (Beanstalk $182M "
            "governance attack, Build Finance DAO attack)."
        ),
        confidence=0.4,
    ),

    # HIGH — Unprotected callback
    Rule(
        rule_id="unprotected-callback",
        title="External callback without access control",
        severity=Severity.HIGH,
        swc_id=None,
        pattern=re.compile(
            r"function\s+(?:onFlashLoan|onERC721Received|onERC1155Received|"
            r"tokensReceived|fallback)\s*\("
            r"(?![\s\S]{0,300}require\s*\(\s*msg\.sender)",
            re.DOTALL,
        ),
        description=(
            "Callback function (onFlashLoan, onERC721Received, onERC1155Received, "
            "tokensReceived, fallback) does not verify msg.sender within the first "
            "~300 characters. Anyone can call the callback directly, potentially "
            "triggering unintended state changes or draining funds. Add "
            "require(msg.sender == expectedCaller) at the start."
        ),
        confidence=0.45,
    ),

    # HIGH — Price donation attack
    Rule(
        rule_id="price-donation-attack",
        title="balanceOf(address(this)) used for accounting — donation attack",
        severity=Severity.HIGH,
        swc_id=None,
        pattern=re.compile(
            r"balanceOf\s*\(\s*address\s*\(\s*this\s*\)\s*\)",
        ),
        description=(
            "Using balanceOf(address(this)) for internal accounting allows anyone to "
            "donate tokens/ETH directly to the contract and manipulate share prices, "
            "reserves, or exchange rates. This is the root cause of ERC-4626 inflation "
            "attacks and many vault exploits. Track internal balances with storage "
            "variables instead of relying on actual token balances."
        ),
        confidence=0.5,
    ),

    # HIGH — Missing reentrancy guard with callback
    Rule(
        rule_id="missing-reentrancy-guard-with-callback",
        title="External call with callback potential but no ReentrancyGuard",
        severity=Severity.HIGH,
        swc_id="SWC-107",
        pattern=re.compile(
            r"\.call\{[^}]*\}"
            r"[\s\S]{0,2000}"
            r"(?:onERC|tokensReceived)"
            r"(?![\s\S]{0,2000}(?:nonReentrant|ReentrancyGuard))",
            re.DOTALL,
        ),
        description=(
            "Contract contains both low-level .call{} and ERC callback handlers "
            "(onERC721Received, onERC1155Received, tokensReceived) but does not use "
            "nonReentrant modifier or ReentrancyGuard. The callback can re-enter "
            "the contract during the external call, leading to state corruption. "
            "Apply OpenZeppelin's ReentrancyGuard to all state-modifying functions."
        ),
        confidence=0.4,
    ),

    # MEDIUM — Unchecked array access
    Rule(
        rule_id="unchecked-array-access",
        title="Array write/delete with unchecked index",
        severity=Severity.MEDIUM,
        swc_id=None,
        pattern=re.compile(
            r"(?:delete\s+\w+\s*\[\s*\w+\s*\]|\w+\s*\[\s*\w+\s*\]\s*=)",
        ),
        description=(
            "Array element is written or deleted using an index that may not be "
            "bounds-checked. In Solidity 0.8+ this reverts with a panic, but in "
            "unchecked{} blocks or older versions it can corrupt storage. Verify the "
            "index is validated against the array length before access."
        ),
        confidence=0.3,
    ),

    # MEDIUM — Centralization risk
    Rule(
        rule_id="centralization-single-admin",
        title="Centralization risk — onlyOwner/onlyAdmin on multiple functions",
        severity=Severity.MEDIUM,
        swc_id=None,
        pattern=re.compile(r"\bonlyOwner\b"),
        description=(
            "Function is gated by onlyOwner, indicating a single EOA or multisig "
            "controls critical contract functionality. If the owner key is compromised "
            "or lost, the contract may be drained or become unusable. Consider "
            "role-based access (AccessControl), timelocks, and multi-sig governance "
            "for critical operations."
        ),
        confidence=0.25,
    ),

    # MEDIUM — Missing contract existence check
    Rule(
        rule_id="missing-contract-existence-check",
        title="Low-level call without contract existence check",
        severity=Severity.MEDIUM,
        swc_id=None,
        pattern=re.compile(
            r"\.call\{[^}]*\}\s*\("
            r"(?![\s\S]{0,300}(?:isContract|extcodesize|code\.length))",
            re.DOTALL,
        ),
        description=(
            "Low-level .call{} to an address without checking if a contract exists "
            "at that address. Calls to EOAs or self-destructed contracts silently "
            "succeed, returning true with empty returndata. Check address.code.length "
            "> 0 or use Address.isContract() before the call."
        ),
        confidence=0.35,
    ),

    # MEDIUM — Approve without reset to zero
    Rule(
        rule_id="token-approval-to-zero-first",
        title="ERC-20 approve() without resetting to zero first",
        severity=Severity.MEDIUM,
        swc_id=None,
        pattern=re.compile(
            r"\.approve\s*\(\s*\w+\s*,\s*(?!0\s*[,\)])[\w.]+",
        ),
        description=(
            "ERC-20 approve() is called with a non-zero value without first resetting "
            "allowance to 0. Non-standard tokens (USDT, KNC) require the allowance to "
            "be 0 before setting a new value, otherwise the transaction reverts. Use "
            "safeApprove(0) followed by safeApprove(amount), or use safeIncreaseAllowance."
        ),
        confidence=0.3,
    ),

    # MEDIUM — msg.value in loop (SWC-126)
    Rule(
        rule_id="msg-value-in-loop",
        title="msg.value reused inside a loop — double-spend risk",
        severity=Severity.MEDIUM,
        swc_id="SWC-126",
        pattern=re.compile(
            r"(?:for|while)\s*\([^)]*\)\s*\{[^}]*msg\.value",
            re.DOTALL,
        ),
        description=(
            "msg.value is referenced inside a loop body. Since msg.value stays "
            "constant throughout the transaction, each iteration uses the full "
            "msg.value rather than a fraction of it. This allows an attacker to "
            "effectively multiply their ETH by the number of iterations. Track "
            "remaining value in a local variable and decrement per iteration."
        ),
        confidence=0.6,
    ),

    # MEDIUM — Unsafe integer downcast
    Rule(
        rule_id="unsafe-downcast",
        title="Unsafe integer downcast — silent truncation risk",
        severity=Severity.MEDIUM,
        swc_id=None,
        pattern=re.compile(
            r"(?:uint8|uint16|uint32|uint64|uint128|int8|int16|int32|int64|int128)"
            r"\s*\(\s*[a-zA-Z_]\w*\s*\)",
        ),
        description=(
            "Casting a larger integer type to a smaller one (e.g. uint256 to uint128) "
            "silently truncates the value in Solidity <0.8 and in unchecked{} blocks. "
            "Even in Solidity 0.8+, explicit type conversion does NOT revert on overflow "
            "— only arithmetic operations do. Use OpenZeppelin's SafeCast library to "
            "get revert-on-overflow behavior for type conversions."
        ),
        confidence=0.35,
    ),

    # MEDIUM — Sandwich-vulnerable swap
    Rule(
        rule_id="sandwich-vulnerable-swap",
        title="Swap with zero slippage protection — sandwich attack",
        severity=Severity.MEDIUM,
        swc_id=None,
        pattern=re.compile(
            r"amountOutMin\s*(?:=|:)\s*0\b",
        ),
        description=(
            "amountOutMin is hardcoded to 0, meaning the swap accepts any output "
            "amount including near-zero. This makes the transaction trivially "
            "sandwichable: an attacker can front-run with a large trade to move the "
            "price, let this swap execute at a terrible rate, then back-run to "
            "capture the profit. Always derive amountOutMin from a recent price "
            "quote with a reasonable slippage tolerance (e.g. 0.5-1%)."
        ),
        confidence=0.5,
    ),

    # MEDIUM — Cross-chain replay
    Rule(
        rule_id="cross-chain-replay",
        title="Signature hash without chain ID — cross-chain replay",
        severity=Severity.MEDIUM,
        swc_id=None,
        pattern=re.compile(
            r"keccak256\s*\(\s*abi\.encode"
            r"(?![\s\S]{0,500}(?:block\.chainid|chainId|chain_id|DOMAIN_SEPARATOR))",
            re.DOTALL,
        ),
        description=(
            "keccak256(abi.encode(...)) constructs a message hash without including "
            "block.chainid or a chain-specific domain separator. Signatures over this "
            "hash can be replayed on other EVM chains (mainnet, L2s, forks). Include "
            "block.chainid in the hash or use EIP-712 DOMAIN_SEPARATOR which includes "
            "the chain ID automatically."
        ),
        confidence=0.4,
    ),

    # MEDIUM — Proxy function selector clash
    Rule(
        rule_id="proxy-function-clash",
        title="Proxy with own functions — selector clash risk",
        severity=Severity.MEDIUM,
        swc_id=None,
        pattern=re.compile(
            r"(?:fallback|receive)\s*\(\s*\)\s+external"
            r"[\s\S]{0,3000}"
            r"function\s+\w+\s*\([^)]*\)\s+(?:external|public)"
            r"[\s\S]{0,3000}"
            r"function\s+\w+\s*\([^)]*\)\s+(?:external|public)"
            r"[\s\S]{0,3000}"
            r"function\s+\w+\s*\([^)]*\)\s+(?:external|public)",
            re.DOTALL,
        ),
        description=(
            "Contract defines a fallback() alongside multiple public/external "
            "functions. In a proxy pattern, function selectors in the proxy can "
            "shadow (clash with) implementation selectors, causing calls to silently "
            "execute the wrong function. Use transparent proxy pattern (admin-only "
            "proxy functions) or UUPS (no proxy-level functions) to avoid clashes."
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
