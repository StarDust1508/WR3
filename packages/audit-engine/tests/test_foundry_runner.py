import json
from pathlib import Path

import pytest

from audit_engine.poc.foundry_runner import ForgeTestResult, FoundryRunner


def test_parse_passing_json() -> None:
    payload = {
        "test/PoC.t.sol:PoC": {
            "test_results": {
                "testExploit()": {"status": "Success", "reason": None}
            }
        }
    }
    out = FoundryRunner._parse(
        stdout=json.dumps(payload), stderr="", return_code=0
    )
    assert out.installed is True
    assert out.compiled is True
    assert out.passed is True
    assert out.test_failures == []


def test_parse_failing_json_collects_reason() -> None:
    payload = {
        "test/PoC.t.sol:PoC": {
            "test_results": {
                "testExploit()": {
                    "status": "Failure",
                    "reason": "assertion: balance unchanged",
                }
            }
        }
    }
    out = FoundryRunner._parse(
        stdout=json.dumps(payload), stderr="", return_code=1
    )
    assert out.passed is False
    assert out.test_failures
    assert "balance unchanged" in out.test_failures[0]
    assert out.revert_reason == "assertion: balance unchanged"


def test_parse_compile_error() -> None:
    out = FoundryRunner._parse(
        stdout="garbage output not json",
        stderr="Error: ParserError: Expected ';' at line 5",
        return_code=1,
    )
    assert out.installed is True
    assert out.passed is False
    assert any("Expected ';'" in f for f in out.test_failures)


def test_not_installed_singleton_shape() -> None:
    r = ForgeTestResult.not_installed()
    assert r.installed is False
    assert r.passed is False
    assert "not available" in r.short_diagnostic or "not installed" in r.short_diagnostic


def test_short_diagnostic_compile_error_keeps_tail() -> None:
    out = ForgeTestResult(
        installed=True,
        compiled=False,
        passed=False,
        raw_stdout="",
        raw_stderr="Error: " + "x" * 3000,
        test_failures=[],
        revert_reason=None,
        return_code=1,
    )
    diag = out.short_diagnostic
    assert diag.startswith("COMPILE ERROR")
    assert len(diag) < 1700


@pytest.mark.asyncio
async def test_run_returns_not_installed_when_forge_missing(tmp_path: Path) -> None:
    runner = FoundryRunner(forge_bin="this-binary-does-not-exist-wr3")
    result = await runner.run(
        workspace=tmp_path,
        target_source="contract X {}",
        test_source="contract T {}",
    )
    assert result.installed is False
    assert result.passed is False
    # Workspace files should still have been written.
    assert (tmp_path / "src" / "Contract.sol").exists()
    assert (tmp_path / "test" / "PoC.t.sol").exists()
    assert (tmp_path / "foundry.toml").exists()
