"""LLM-driven Foundry PoC generator with retry loop.

For one finding, runs up to N attempts:
    attempt 1: prompt LLM to write a Solidity Foundry test that proves the bug
    attempt 2..N: feed the previous attempt + forge output back; LLM revises

A successful test (forge exit 0, all assertions pass) yields PoCOutcome with
validated=True and the artifact path. A persistent failure yields
validated=False with the last test source still saved.

Token control:
    - Cap target source we send to LLM (default 24K chars).
    - Cap retries (default 3 for cost; tunable up to 5 per TZ.md).
    - Skip ENTIRELY if target source is empty or finding is INFO/LOW.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import structlog

from audit_engine.llm import LLMRequest, LLMRouter, Sensitivity
from audit_engine.poc.artifacts import PoCArtifactStore
from audit_engine.poc.foundry_runner import FoundryRunner
from audit_engine.types import Finding, Severity

logger = structlog.get_logger()


_SYSTEM_PROMPT = """You are a senior smart-contract security engineer writing
Foundry tests that prove vulnerabilities.

Output ONLY a single Solidity file. No prose, no markdown fences. The file must
compile with solc 0.8.24 against forge-std and the user-provided target.

Rules for the test file:
  - SPDX + pragma solidity ^0.8.24
  - import "forge-std/Test.sol";
  - import "../src/Contract.sol";  // target lives at src/Contract.sol
  - contract PoC is Test { function testExploit() public { ... } }
  - Use vm.prank / vm.deal / vm.startPrank for setup as needed.
  - Conclude with an assertion that proves the exploit (e.g. funds moved,
    state corrupted, access bypassed). Failing assertion === bug NOT proven.
  - Keep it minimal. No external deps beyond forge-std.
"""

_USER_TEMPLATE = """TARGET CONTRACT (lives at src/Contract.sol):
```solidity
{source}
```

FINDING TO EXPLOIT:
  id:         {finding_id}
  title:      {title}
  severity:   {severity}
  engine:     {engine}
  line:       {line}
  description: {description}

Write a Foundry test that proves this finding is exploitable.
"""

_RETRY_TEMPLATE = """Your previous PoC ({previous_path}) did not work.

PREVIOUS ATTEMPT:
```solidity
{previous_source}
```

FORGE OUTPUT (truncated):
{forge_output}

Revise the test. Do not repeat the same mistake. Address the actual failure
above. Output ONLY the corrected Solidity file.
"""

_MD_FENCE = re.compile(r"^```(?:solidity|sol)?\s*|\s*```$", re.MULTILINE | re.DOTALL)


@dataclass
class PoCOutcome:
    finding_id: str
    validated: bool
    attempts: int
    artifact_path: str | None
    diagnostic: str  # last forge diagnostic or skip reason


class PoCGenerator:
    """Drives a small retry-loop for one finding at a time."""

    def __init__(
        self,
        *,
        llm: LLMRouter | None = None,
        runner: FoundryRunner | None = None,
        store: PoCArtifactStore | None = None,
        max_attempts: int = 3,
        max_source_chars: int = 24_000,
    ) -> None:
        self.llm = llm or LLMRouter()
        self.runner = runner or FoundryRunner()
        self.store = store or PoCArtifactStore()
        self.max_attempts = max(1, max_attempts)
        self.max_source_chars = max_source_chars

    def should_attempt(self, finding: Finding) -> bool:
        if finding.dismissed:
            return False
        return finding.severity in (Severity.HIGH, Severity.CRITICAL)

    async def generate(
        self,
        *,
        scan_id: str,
        finding: Finding,
        target_source: str,
    ) -> PoCOutcome:
        if not target_source.strip():
            return PoCOutcome(
                finding_id=finding.id,
                validated=False,
                attempts=0,
                artifact_path=None,
                diagnostic="empty target source",
            )

        workspace = self.store.workspace_for(scan_id=scan_id, finding_id=finding.id)
        source = target_source[: self.max_source_chars]

        previous_source: str | None = None
        previous_diagnostic = ""

        for attempt in range(1, self.max_attempts + 1):
            messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
            if attempt == 1:
                messages.append(
                    {
                        "role": "user",
                        "content": _USER_TEMPLATE.format(
                            source=source,
                            finding_id=finding.id,
                            title=finding.title,
                            severity=finding.severity.value,
                            engine=finding.source_engine,
                            line=finding.line or 0,
                            description=finding.description[:1500],
                        ),
                    }
                )
            else:
                messages += [
                    {
                        "role": "user",
                        "content": _USER_TEMPLATE.format(
                            source=source,
                            finding_id=finding.id,
                            title=finding.title,
                            severity=finding.severity.value,
                            engine=finding.source_engine,
                            line=finding.line or 0,
                            description=finding.description[:1500],
                        ),
                    },
                    {"role": "assistant", "content": previous_source or ""},
                    {
                        "role": "user",
                        "content": _RETRY_TEMPLATE.format(
                            previous_path=f"test/PoC.attempt{attempt - 1}.t.sol",
                            previous_source=(previous_source or "")[: self.max_source_chars // 2],
                            forge_output=previous_diagnostic[:4000],
                        ),
                    },
                ]

            try:
                raw = await self.llm.complete(
                    LLMRequest(
                        messages=messages,
                        sensitivity=Sensitivity.HIGH,
                        temperature=0.2,
                        max_tokens=3500,
                    )
                )
            except Exception as e:
                logger.warning("poc.llm_failed", error=str(e), finding=finding.id)
                return PoCOutcome(
                    finding_id=finding.id,
                    validated=False,
                    attempts=attempt - 1,
                    artifact_path=None,
                    diagnostic=f"LLM error: {e}",
                )

            test_src = _strip_fences(raw)
            test_path = self.store.save_test(workspace=workspace, content=test_src, attempt=attempt)

            forge_result = await self.runner.run(
                workspace=workspace,
                target_source=source,
                test_source=test_src,
            )
            log_body = (
                f"$ forge test --json -vv\nreturn_code={forge_result.return_code}\n\n"
                f"STDOUT:\n{forge_result.raw_stdout}\n\nSTDERR:\n{forge_result.raw_stderr}\n"
            )
            self.store.save_log(workspace=workspace, attempt=attempt, body=log_body)

            if not forge_result.installed:
                # Skip whole feature: forge missing on host. No retries help here.
                return PoCOutcome(
                    finding_id=finding.id,
                    validated=False,
                    attempts=attempt,
                    artifact_path=self.store.relative(test_path),
                    diagnostic="forge not installed",
                )

            if forge_result.passed:
                logger.info("poc.validated", finding=finding.id, attempt=attempt)
                return PoCOutcome(
                    finding_id=finding.id,
                    validated=True,
                    attempts=attempt,
                    artifact_path=self.store.relative(test_path),
                    diagnostic=forge_result.short_diagnostic,
                )

            previous_source = test_src
            previous_diagnostic = forge_result.short_diagnostic
            logger.info(
                "poc.attempt_failed",
                finding=finding.id,
                attempt=attempt,
                compiled=forge_result.compiled,
            )

        # Exhausted retries — return last attempt as artifact, validated=False.
        return PoCOutcome(
            finding_id=finding.id,
            validated=False,
            attempts=self.max_attempts,
            artifact_path=self.store.relative(workspace / f"PoC.attempt{self.max_attempts}.t.sol"),
            diagnostic=previous_diagnostic or "exhausted retries",
        )


def _strip_fences(raw: str) -> str:
    """Remove ```solidity / ``` fences that the LLM may add despite instructions."""
    cleaned = raw.strip()
    cleaned = _MD_FENCE.sub("", cleaned)
    return cleaned.strip()
