"""Ingestion unit tests — explorer JSON parsing only (no real HTTP)."""

from audit_engine.ingestion.fetcher import SourceFetcher


def test_parse_single_file() -> None:
    fetcher = SourceFetcher()
    bundle = fetcher._parse(
        {
            "SourceCode": "pragma solidity ^0.8.0;\ncontract A {}",
            "ContractName": "A",
            "CompilerVersion": "v0.8.20+commit.a1b79de6",
            "OptimizationUsed": "1",
            "Runs": "200",
            "Proxy": "0",
        },
        address="0x" + "a" * 40,
        network="base",
    )
    assert bundle.contract_name == "A"
    assert bundle.flattened_source is not None
    assert "contract A" in bundle.flattened_source
    assert bundle.optimization_used is True
    assert bundle.runs == 200


def test_parse_standard_json_double_braces() -> None:
    fetcher = SourceFetcher()
    standard = (
        '{{"language":"Solidity","sources":{'
        '"contracts/A.sol":{"content":"contract A {}"},'
        '"contracts/B.sol":{"content":"contract B {}"}'
        '}}}'
    )
    bundle = fetcher._parse(
        {
            "SourceCode": standard,
            "ContractName": "A",
            "CompilerVersion": "v0.8.20",
            "OptimizationUsed": "0",
        },
        address="0x" + "b" * 40,
        network="ethereum",
    )
    assert set(bundle.files.keys()) == {"contracts/A.sol", "contracts/B.sol"}
    assert "contract A" in bundle.files["contracts/A.sol"]
    assert bundle.flattened_source is None


def test_primary_source_joins_files() -> None:
    fetcher = SourceFetcher()
    bundle = fetcher._parse(
        {
            "SourceCode": '{"sources":{"A.sol":{"content":"contract A {}"}}}',
            "ContractName": "A",
            "CompilerVersion": "v0.8.20",
            "OptimizationUsed": "0",
        },
        address="0x" + "c" * 40,
        network="base",
    )
    assert "contract A" in bundle.primary_source
