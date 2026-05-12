"""Solana program metadata via public JSON-RPC.

Why this exists:
    There is NO Etherscan-equivalent for verified Solana source. solana-verify
    builds exist on GitHub for some programs but there's no public API to
    query. So source code for Solana scans must come from the user (pasted
    into the form) — the regular EVM `SourceFetcher.fetch()` correctly
    returns None for `network="solana"`.

    Metadata, however, IS available on-chain and free. This module fetches:
      - Executable status (is this an actual program?)
      - Loader (BPFLoader2 = frozen, BPFLoaderUpgradeable = upgradeable)
      - For upgradeable programs: upgrade authority address + slot when it
        was last upgraded

Why it matters for an audit:
    A program with a non-None upgrade authority is a centralisation risk
    that wr3's scoring needs to surface (Tokenomics axis). The presence of
    a recent upgrade slot is also an audit signal — "they shipped a change
    last week and want it scanned".

Provider:
    `https://api.mainnet-beta.solana.com` — Solana Foundation's public RPC.
    Free, rate-limited but generous. No key required. We use a 15s timeout
    and tenacity retry on transient errors.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = structlog.get_logger()


_DEFAULT_RPC = "https://api.mainnet-beta.solana.com"
_BPF_LOADER_FROZEN = "BPFLoader2111111111111111111111111111111111"
_BPF_LOADER_UPGRADEABLE = "BPFLoaderUpgradeab1e11111111111111111111111"

# Length of the upgradeable ProgramData header.
# Layout per solana-program loader-upgradeable:
#   discriminator (4B LE) | slot (8B LE) | option<Pubkey>(1B + 32B) | code...
# The discriminator for ProgramData is 3 (LittleEndian u32).
_PROGDATA_DISCRIMINATOR = 3
_PROGDATA_HEADER_LEN = 4 + 8 + 1 + 32  # = 45 bytes


@dataclass
class SolanaProgramMetadata:
    """What we know about a Solana program from on-chain reads alone."""

    address: str
    executable: bool
    loader: str | None  # the program's owner field
    upgradeable: bool
    upgrade_authority: str | None
    last_upgrade_slot: int | None

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "executable": self.executable,
            "loader": self.loader,
            "upgradeable": self.upgradeable,
            "upgrade_authority": self.upgrade_authority,
            "last_upgrade_slot": self.last_upgrade_slot,
        }


class SolanaMetadataFetcher:
    """Tiny Solana JSON-RPC client for program-metadata reads."""

    def __init__(self, *, rpc_url: str | None = None, timeout: float = 15.0) -> None:
        self.rpc_url = rpc_url or os.getenv("SOLANA_RPC_URL", _DEFAULT_RPC)
        self.timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True,
    )
    async def _get_account_info(
        self, address: str, *, encoding: str = "base64"
    ) -> dict | None:
        """One getAccountInfo call. Returns the `value` dict or None."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAccountInfo",
            "params": [address, {"encoding": encoding}],
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(self.rpc_url, json=payload)
            r.raise_for_status()
            data = r.json()
        if "error" in data:
            logger.warning("solana.rpc_error", error=data["error"], address=address)
            return None
        return (data.get("result") or {}).get("value")

    async def fetch(self, address: str) -> SolanaProgramMetadata | None:
        """Best-effort metadata. Returns None if the account doesn't exist."""
        program = await self._get_account_info(address)
        if program is None:
            return None

        executable = bool(program.get("executable"))
        loader = program.get("owner")

        upgradeable = executable and loader == _BPF_LOADER_UPGRADEABLE
        upgrade_authority: str | None = None
        last_upgrade_slot: int | None = None

        if upgradeable:
            # The program account's data for an upgradeable program is
            # [discriminator=2 LE u32] [option<Pubkey> ProgramData address].
            # We can derive ProgramData via PDA, but the loader stores it
            # in the program account's data directly: bytes 4..36.
            raw = program.get("data")
            program_data_address = _parse_progdata_pointer(raw)
            if program_data_address:
                progdata = await self._get_account_info(program_data_address)
                if progdata is not None:
                    raw_pd = progdata.get("data")
                    parsed = _parse_progdata_header(raw_pd)
                    if parsed:
                        last_upgrade_slot, upgrade_authority = parsed

        return SolanaProgramMetadata(
            address=address,
            executable=executable,
            loader=loader,
            upgradeable=upgradeable,
            upgrade_authority=upgrade_authority,
            last_upgrade_slot=last_upgrade_slot,
        )


def _decode_data(raw) -> bytes | None:
    """Account data comes as [base64_string, "base64"] or [b58_string, "base58"]."""
    if not isinstance(raw, list) or len(raw) < 2:
        return None
    content, encoding = raw[0], raw[1]
    if not isinstance(content, str):
        return None
    if encoding == "base64":
        try:
            return base64.b64decode(content)
        except Exception:
            return None
    return None  # we only ever request base64


def _parse_progdata_pointer(raw) -> str | None:
    """Read the ProgramData address out of an upgradeable program's data.

    Layout: [discriminator: u32 LE = 2] [Pubkey: 32B] = 36 bytes.
    """
    blob = _decode_data(raw)
    if blob is None or len(blob) < 36:
        return None
    discriminator = int.from_bytes(blob[:4], "little")
    if discriminator != 2:
        return None
    pubkey_bytes = blob[4:36]
    try:
        from base58 import b58encode
        return b58encode(pubkey_bytes).decode("ascii")
    except ImportError:
        # Fall back to a minimal base58 encoder so we don't drag a dep in.
        return _b58encode(pubkey_bytes)


def _parse_progdata_header(raw) -> tuple[int, str | None] | None:
    """Parse (slot, upgrade_authority_or_None) from a ProgramData account.

    Returns None if discriminator isn't ProgramData. Empty option means the
    program has been made immutable.
    """
    blob = _decode_data(raw)
    if blob is None or len(blob) < _PROGDATA_HEADER_LEN:
        return None
    discriminator = int.from_bytes(blob[:4], "little")
    if discriminator != _PROGDATA_DISCRIMINATOR:
        return None
    slot = int.from_bytes(blob[4:12], "little")
    has_authority = blob[12] == 1
    if not has_authority:
        return slot, None
    authority_bytes = blob[13:45]
    return slot, _b58encode(authority_bytes)


# --- Minimal base58 ----------------------------------------------------------

_B58_ALPHABET = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58encode(b: bytes) -> str:
    """Standard Bitcoin/Solana base58 encoder.

    Inlined to avoid pulling base58 as a dep. ~6 lines of arithmetic.
    """
    n = int.from_bytes(b, "big")
    out = bytearray()
    while n > 0:
        n, rem = divmod(n, 58)
        out.append(_B58_ALPHABET[rem])
    # Leading zero bytes → leading '1' in base58.
    pad = 0
    for byte in b:
        if byte == 0:
            pad += 1
        else:
            break
    return ("1" * pad) + out[::-1].decode("ascii")
