"""Watcher repository — focus on the pure-logic seams.

`compute_source_hash` is deterministic and side-effect free; the DB ops
are covered by the live e2e check documented in the W12 commit message
(USDC → baseline → forced mismatch → 'changed' outcome).
"""

from __future__ import annotations

from wr3_api.services.watch_repository import compute_source_hash


def test_hash_is_deterministic() -> None:
    a = compute_source_hash("contract Foo {}")
    b = compute_source_hash("contract Foo {}")
    assert a == b
    assert len(a) == 64


def test_hash_detects_whitespace_changes() -> None:
    """Source code formatting changes should flip the hash. Etherscan
    serves exactly what the verifier submitted, so even a re-format that
    keeps identical bytecode WILL show up here. That's intentional: if
    the verifier changed, that's news the user might want to know about.
    """
    a = compute_source_hash("function foo() {}")
    b = compute_source_hash("function foo()  {}")  # extra space
    assert a != b


def test_hash_handles_none() -> None:
    """NULL source must hash to a stable sentinel, not crash."""
    a = compute_source_hash(None)
    b = compute_source_hash("")
    # Both empty inputs → identical hash (sha256 of "")
    assert a == b == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_hash_handles_unicode() -> None:
    a = compute_source_hash("// привет мир\ncontract Foo {}")
    b = compute_source_hash("// привет мир\ncontract Foo {}")
    assert a == b
    assert len(a) == 64
