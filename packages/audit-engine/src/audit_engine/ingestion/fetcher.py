"""Multi-explorer verified-source fetcher.

All Etherscan-family explorers (Etherscan / BscScan / Basescan / Arbiscan)
share the same `getsourcecode` API shape. We route by network → explorer
base URL + API key.

Solana is handled separately via Solana Explorer / Solscan API (TODO).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Literal

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = structlog.get_logger()

Network = Literal["ethereum", "base", "arbitrum", "bsc", "solana"]


_EXPLORER_CONFIG: dict[Network, dict[str, str]] = {
    "ethereum": {
        "base_url": "https://api.etherscan.io/api",
        "key_env": "ETHERSCAN_API_KEY",
    },
    "base": {
        "base_url": "https://api.basescan.org/api",
        "key_env": "BASESCAN_API_KEY",
    },
    "arbitrum": {
        "base_url": "https://api.arbiscan.io/api",
        "key_env": "ARBISCAN_API_KEY",
    },
    "bsc": {
        "base_url": "https://api.bscscan.com/api",
        "key_env": "BSCSCAN_API_KEY",
    },
}


_ADDRESS_EVM = re.compile(r"^0x[a-fA-F0-9]{40}$")


@dataclass
class SourceBundle:
    """Verified-source pull result, normalized across explorers."""

    address: str
    network: Network
    contract_name: str
    compiler_version: str
    optimization_used: bool
    runs: int | None = None
    # If verified as single file:
    flattened_source: str | None = None
    # If verified as multi-file (standard-json or sources dict):
    files: dict[str, str] = field(default_factory=dict)
    abi: str | None = None
    proxy: bool = False
    implementation: str | None = None

    @property
    def primary_source(self) -> str:
        """Return single-file source for analyzers that want a flat input."""
        if self.flattened_source:
            return self.flattened_source
        if self.files:
            # Join files with delimiter; analyzers that need file boundaries
            # should use .files directly.
            return "\n\n".join(
                f"// === {name} ===\n{content}" for name, content in self.files.items()
            )
        return ""


class SourceFetcher:
    """Fetches verified source from an explorer for a given network."""

    def __init__(self, *, timeout: float = 30.0) -> None:
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True,
    )
    async def fetch(self, *, address: str, network: Network) -> SourceBundle | None:
        if network == "solana":
            logger.info("ingestion.solana.not_yet")
            return None

        if not _ADDRESS_EVM.match(address):
            logger.warning("ingestion.invalid_address", address=address, network=network)
            return None

        cfg = _EXPLORER_CONFIG.get(network)
        if cfg is None:
            logger.warning("ingestion.unsupported_network", network=network)
            return None

        api_key = os.getenv(cfg["key_env"], "")
        params = {
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
        }
        if api_key:
            params["apikey"] = api_key

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.get(cfg["base_url"], params=params)
            r.raise_for_status()
            data = r.json()

        if data.get("status") not in ("1", 1):
            logger.warning(
                "ingestion.api_error",
                network=network,
                message=data.get("message"),
                result=str(data.get("result"))[:200],
            )
            return None

        results = data.get("result") or []
        if not results:
            return None
        item = results[0]

        if not item.get("SourceCode"):
            logger.info("ingestion.not_verified", address=address, network=network)
            return None

        bundle = self._parse(item, address=address, network=network)
        logger.info(
            "ingestion.success",
            address=address,
            network=network,
            files=len(bundle.files),
            flat_len=len(bundle.flattened_source or ""),
        )
        return bundle

    def _parse(
        self, item: dict, *, address: str, network: Network
    ) -> SourceBundle:
        source_field = item.get("SourceCode", "") or ""
        files: dict[str, str] = {}
        flat: str | None = None

        # Etherscan sometimes wraps Standard JSON Input with double braces.
        s = source_field
        if s.startswith("{{") and s.endswith("}}"):
            s = s[1:-1]
        try:
            if s.lstrip().startswith("{"):
                parsed = json.loads(s)
                sources = parsed.get("sources") or parsed
                if isinstance(sources, dict):
                    for path, blob in sources.items():
                        if isinstance(blob, dict) and "content" in blob:
                            files[path] = blob["content"]
                        elif isinstance(blob, str):
                            files[path] = blob
        except json.JSONDecodeError:
            pass

        if not files:
            flat = source_field

        return SourceBundle(
            address=address,
            network=network,
            contract_name=item.get("ContractName", "") or "Unknown",
            compiler_version=item.get("CompilerVersion", "") or "",
            optimization_used=str(item.get("OptimizationUsed", "0")) == "1",
            runs=_safe_int(item.get("Runs")),
            flattened_source=flat,
            files=files,
            abi=item.get("ABI") or None,
            proxy=str(item.get("Proxy", "0")) == "1",
            implementation=item.get("Implementation") or None,
        )


def _safe_int(v: object) -> int | None:
    try:
        return int(v) if v not in (None, "", "0") else None
    except (TypeError, ValueError):
        return None


# Convenience module-level function.
async def fetch_source(address: str, network: Network) -> SourceBundle | None:
    return await SourceFetcher().fetch(address=address, network=network)
