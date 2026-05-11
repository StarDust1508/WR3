import pytest

from audit_engine.analyzers.baseline import BaselineAnalyzer
from audit_engine.types import Severity


@pytest.mark.asyncio
async def test_detects_tx_origin() -> None:
    src = """
    pragma solidity ^0.8.0;
    contract A {
        function withdraw() external {
            require(tx.origin == owner, "no");
        }
    }
    """
    findings = await BaselineAnalyzer().analyze(source=src)
    titles = [f.title for f in findings]
    assert any("tx.origin" in t for t in titles)
    tx = next(f for f in findings if "tx.origin" in f.title)
    assert tx.severity == Severity.HIGH


@pytest.mark.asyncio
async def test_detects_delegatecall() -> None:
    src = """
    contract Proxy {
        function fwd(address t, bytes calldata d) external {
            (bool ok, ) = t.delegatecall(d);
            require(ok);
        }
    }
    """
    findings = await BaselineAnalyzer().analyze(source=src)
    assert any(f.severity == Severity.CRITICAL and "delegatecall" in f.title for f in findings)


@pytest.mark.asyncio
async def test_detects_block_timestamp_randomness() -> None:
    src = """
    contract Lottery {
        function r() external view returns (uint256) {
            return uint256(keccak256(abi.encodePacked(block.timestamp, msg.sender)));
        }
    }
    """
    findings = await BaselineAnalyzer().analyze(source=src)
    assert any("randomness" in f.title.lower() for f in findings)


@pytest.mark.asyncio
async def test_ignores_comments() -> None:
    """Patterns inside comments must not produce findings (false positives)."""
    src = """
    contract A {
        // tx.origin is bad, do not use it
        /* selfdestruct(payable(msg.sender)) — example only */
        function safe() external pure returns (uint256) {
            return 1;
        }
    }
    """
    findings = await BaselineAnalyzer().analyze(source=src)
    assert all("tx.origin" not in f.title for f in findings)
    assert all("selfdestruct" not in f.title.lower() for f in findings)


@pytest.mark.asyncio
async def test_floating_pragma_info() -> None:
    src = "pragma solidity ^0.8.20;\ncontract X {}\n"
    findings = await BaselineAnalyzer().analyze(source=src)
    floating = [f for f in findings if "pragma" in f.title.lower()]
    assert floating
    assert floating[0].severity == Severity.INFO


@pytest.mark.asyncio
async def test_empty_source() -> None:
    assert await BaselineAnalyzer().analyze(source="") == []
