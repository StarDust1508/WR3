"""Solana metadata fetcher — unit tests with mocked Solana JSON-RPC.

We mock the public RPC so tests don't depend on the Solana network and
don't burn the user's rate limit. The byte layouts being parsed
(ProgramData header, program pointer) are tested by constructing real
binary blobs.
"""

from __future__ import annotations

import base64

import httpx
import pytest
import respx

from audit_engine.ingestion.solana_metadata import (
    _BPF_LOADER_FROZEN,
    _BPF_LOADER_UPGRADEABLE,
    SolanaMetadataFetcher,
    _b58encode,
    _parse_progdata_header,
    _parse_progdata_pointer,
)


RPC_URL = "https://api.mainnet-beta.solana.com"


def _rpc_account(*, executable: bool, owner: str, data_b64: str = "") -> dict:
    return {
        "jsonrpc": "2.0",
        "result": {
            "context": {"slot": 12345},
            "value": {
                "data": [data_b64, "base64"],
                "executable": executable,
                "lamports": 1,
                "owner": owner,
                "rentEpoch": 0,
                "space": len(base64.b64decode(data_b64)) if data_b64 else 0,
            },
        },
        "id": 1,
    }


def _make_progdata_blob(slot: int, authority: bytes | None) -> bytes:
    """Build a ProgramData account body the way the BPF loader does."""
    body = (
        (3).to_bytes(4, "little")              # discriminator
        + slot.to_bytes(8, "little")           # slot
        + (b"\x01" + authority if authority else b"\x00" + b"\x00" * 32)
    )
    return body


def _make_program_blob(programdata_pubkey: bytes) -> bytes:
    """Program account body for an upgradeable program: discriminator=2 + ptr."""
    return (2).to_bytes(4, "little") + programdata_pubkey


def test_b58encode_matches_known_pubkey() -> None:
    # All-zero pubkey -> base58 of 32 zero bytes -> "11111111111111111111111111111111"
    out = _b58encode(b"\x00" * 32)
    assert out == "11111111111111111111111111111111"


def test_parse_progdata_header_with_authority() -> None:
    authority = b"\xaa" * 32
    blob = _make_progdata_blob(slot=999, authority=authority)
    raw = [base64.b64encode(blob).decode("ascii"), "base64"]
    parsed = _parse_progdata_header(raw)
    assert parsed is not None
    slot, auth = parsed
    assert slot == 999
    assert auth == _b58encode(authority)


def test_parse_progdata_header_immutable() -> None:
    """No upgrade authority => program is frozen via opt-out."""
    blob = _make_progdata_blob(slot=100, authority=None)
    raw = [base64.b64encode(blob).decode("ascii"), "base64"]
    parsed = _parse_progdata_header(raw)
    assert parsed == (100, None)


def test_parse_progdata_header_wrong_discriminator() -> None:
    blob = (0).to_bytes(4, "little") + b"\x00" * 100
    raw = [base64.b64encode(blob).decode("ascii"), "base64"]
    assert _parse_progdata_header(raw) is None


def test_parse_progdata_pointer_resolves_to_base58() -> None:
    pk = b"\xbb" * 32
    blob = _make_program_blob(pk)
    raw = [base64.b64encode(blob).decode("ascii"), "base64"]
    assert _parse_progdata_pointer(raw) == _b58encode(pk)


@pytest.mark.respx(base_url=RPC_URL)
async def test_fetch_frozen_program() -> None:
    addr = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
    with respx.mock(base_url=RPC_URL) as mock:
        mock.post("").mock(
            return_value=httpx.Response(
                200,
                json=_rpc_account(
                    executable=True,
                    owner=_BPF_LOADER_FROZEN,
                ),
            )
        )
        meta = await SolanaMetadataFetcher(rpc_url=RPC_URL).fetch(addr)

    assert meta is not None
    assert meta.executable is True
    assert meta.loader == _BPF_LOADER_FROZEN
    assert meta.upgradeable is False
    assert meta.upgrade_authority is None
    assert meta.last_upgrade_slot is None


async def test_fetch_upgradeable_program_with_authority() -> None:
    """End-to-end: program -> ProgramData -> upgrade authority + slot."""
    addr = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"

    programdata_pubkey = b"\xcc" * 32
    program_blob = _make_program_blob(programdata_pubkey)
    program_b64 = base64.b64encode(program_blob).decode("ascii")

    authority = b"\xdd" * 32
    progdata_blob = _make_progdata_blob(slot=418976287, authority=authority)
    progdata_b64 = base64.b64encode(progdata_blob).decode("ascii")

    # First call returns the program; second returns the ProgramData PDA.
    responses = [
        httpx.Response(
            200,
            json=_rpc_account(
                executable=True,
                owner=_BPF_LOADER_UPGRADEABLE,
                data_b64=program_b64,
            ),
        ),
        httpx.Response(
            200,
            json=_rpc_account(
                executable=False,
                owner=_BPF_LOADER_UPGRADEABLE,
                data_b64=progdata_b64,
            ),
        ),
    ]
    with respx.mock(base_url=RPC_URL) as mock:
        mock.post("").mock(side_effect=responses)
        meta = await SolanaMetadataFetcher(rpc_url=RPC_URL).fetch(addr)

    assert meta is not None
    assert meta.upgradeable is True
    assert meta.upgrade_authority == _b58encode(authority)
    assert meta.last_upgrade_slot == 418976287


async def test_fetch_nonexistent_account_returns_none() -> None:
    with respx.mock(base_url=RPC_URL) as mock:
        mock.post("").mock(
            return_value=httpx.Response(
                200, json={"jsonrpc": "2.0", "result": {"value": None}, "id": 1}
            )
        )
        meta = await SolanaMetadataFetcher(rpc_url=RPC_URL).fetch("doesnotexist")
    assert meta is None


async def test_fetch_handles_rpc_error_response() -> None:
    with respx.mock(base_url=RPC_URL) as mock:
        mock.post("").mock(
            return_value=httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "error": {"code": -32602, "message": "Invalid params"},
                    "id": 1,
                },
            )
        )
        meta = await SolanaMetadataFetcher(rpc_url=RPC_URL).fetch("bad_address")
    assert meta is None
