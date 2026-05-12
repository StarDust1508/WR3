"""Telegram bot command parser unit tests."""

from __future__ import annotations

from wr3_api.telegram.bot import detect_network_and_address, parse_command


def test_parse_command_drops_bot_suffix() -> None:
    assert parse_command("/scan@wr3_audit_bot 0xabc base") == ("/scan", ["0xabc", "base"])


def test_parse_command_empty() -> None:
    assert parse_command("") == ("", [])
    assert parse_command("   ") == ("", [])


def test_parse_command_lowercases() -> None:
    cmd, _args = parse_command("/SCAN 0xabc")
    assert cmd == "/scan"


def test_detect_address_evm() -> None:
    addr, net = detect_network_and_address(["0x" + "a" * 40, "base"])
    assert addr == "0x" + "a" * 40
    assert net == "base"


def test_detect_address_position_independent() -> None:
    addr, net = detect_network_and_address(["base", "0x" + "b" * 40])
    assert addr == "0x" + "b" * 40
    assert net == "base"


def test_detect_solana_address_inferred_network() -> None:
    sol = "7xLk5GnYR42c4Lh1bX7wMfeJ6jbnf6Wxhq8L4nN3vTtT"
    addr, net = detect_network_and_address([sol])
    assert addr == sol
    assert net == "solana"


def test_detect_returns_none_for_garbage() -> None:
    assert detect_network_and_address(["hello", "world"]) == (None, None)


def test_detect_network_alias_eth_to_ethereum() -> None:
    _addr, net = detect_network_and_address(["eth", "0x" + "c" * 40])
    assert net == "ethereum"


def test_detect_bnb_alias() -> None:
    _addr, net = detect_network_and_address(["bnb", "0x" + "d" * 40])
    assert net == "bsc"
