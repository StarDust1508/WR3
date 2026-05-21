"""Multi-explorer verified-source fetcher.

Uses the Etherscan V2 unified endpoint
    https://api.etherscan.io/v2/api?chainid={id}&...
This is the same single endpoint for all EVM chains, distinguished by
`chainid` (1=eth, 56=bsc, 8453=base, 42161=arbitrum). The V1 per-explorer
endpoints (api.bscscan.com etc) were deprecated by Etherscan in 2024;
all four chains now go through one base URL and one API key.

Free tier: 5 calls/sec, 100k calls/day. Sign up at
https://etherscan.io/apis — the resulting key works for all listed
chains.

Solana is intentionally NOT served by this fetcher:
  There is no public API equivalent of Etherscan's verified-source lookup
  for Solana programs. solana-verified-builds exists on GitHub but isn't
  exposed as a queryable index. Solana scans therefore require the user
  to paste source code into the form; on-chain metadata (executable,
  upgrade authority, last upgrade slot) is enriched separately by
  `audit_engine.ingestion.solana_metadata.SolanaMetadataFetcher`, which
  uses the free Solana JSON-RPC.
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


# Etherscan V2 multichain endpoint — one base URL for all EVM chains,
# distinguished by `chainid`. One API key works for all listed chains.
_ETHERSCAN_V2_BASE_URL = "https://api.etherscan.io/v2/api"

_CHAIN_IDS: dict[Network, int] = {
    "ethereum": 1,
    "bsc": 56,
    "arbitrum": 42161,
    "base": 8453,
}

# Per-network env key fallback. Primary is ETHERSCAN_API_KEY (V2 unified).
_KEY_ENV_PRIORITY: dict[Network, list[str]] = {
    "ethereum": ["ETHERSCAN_API_KEY"],
    "bsc": ["ETHERSCAN_API_KEY", "BSCSCAN_API_KEY"],
    "arbitrum": ["ETHERSCAN_API_KEY", "ARBISCAN_API_KEY"],
    "base": ["ETHERSCAN_API_KEY", "BASESCAN_API_KEY"],
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
    """Fetches verified source from Etherscan V2 multichain endpoint."""

    def __init__(self, *, timeout: float = 30.0) -> None:
        self._timeout = timeout

    @staticmethod
    def _resolve_key(network: Network) -> str | None:
        """Try primary `ETHERSCAN_API_KEY` then per-network legacy fallbacks."""
        for env in _KEY_ENV_PRIORITY.get(network, ["ETHERSCAN_API_KEY"]):
            value = os.getenv(env, "").strip()
            if value:
                return value
        return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True,
    )
    async def fetch(self, *, address: str, network: Network) -> SourceBundle | None:
        if network == "solana":
            # Source code for Solana programs isn't available via any public
            # API — verified-source registries exist only on GitHub. The
            # pipeline handles this by requiring the user to paste source,
            # and enriches on-chain metadata via SolanaMetadataFetcher.
            logger.info("ingestion.solana.source_must_be_pasted", address=address)
            return None

        if not _ADDRESS_EVM.match(address):
            logger.warning("ingestion.invalid_address", address=address, network=network)
            return None

        chain_id = _CHAIN_IDS.get(network)
        if chain_id is None:
            logger.warning("ingestion.unsupported_network", network=network)
            return None

        api_key = self._resolve_key(network)
        if not api_key:
            logger.warning(
                "ingestion.missing_api_key",
                network=network,
                hint="set ETHERSCAN_API_KEY (free, etherscan.io/apis)",
            )
            return None

        params = {
            "chainid": str(chain_id),
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
            "apikey": api_key,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.get(_ETHERSCAN_V2_BASE_URL, params=params)
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


async def fetch_source_with_implementation(
    address: str, network: Network
) -> SourceBundle | None:
    """Fetch source and, if the contract is a proxy, also fetch the implementation.

    Most DeFi contracts (70%+) are behind proxies (TransparentProxy, UUPS, EIP-1967).
    The proxy itself is just a `fallback() { delegatecall(impl) }` stub — the real
    business logic lives in the implementation contract. Without fetching the
    implementation, we audit a 20-line stub instead of the actual code.

    Strategy:
      1. Fetch the proxy's source from Etherscan.
      2. If Etherscan reports `Proxy=1` and `Implementation=0x...`, fetch that too.
      3. Merge: implementation becomes the primary_source, proxy source is preserved
         in metadata for storage layout analysis.
    """
    fetcher = SourceFetcher()
    bundle = await fetcher.fetch(address=address, network=network)
    if bundle is None:
        return None

    if not bundle.proxy or not bundle.implementation:
        return bundle

    # Fetch implementation contract source.
    impl_address = bundle.implementation
    logger.info(
        "ingestion.fetching_implementation",
        proxy=address,
        implementation=impl_address,
        network=network,
    )
    impl_bundle = await fetcher.fetch(address=impl_address, network=network)
    if impl_bundle is None:
        logger.warning(
            "ingestion.implementation_not_verified",
            proxy=address,
            implementation=impl_address,
        )
        return bundle

    # Merge: implementation source becomes primary, proxy preserved in metadata.
    proxy_source = bundle.primary_source
    impl_source = impl_bundle.primary_source

    # Combine files from both proxy and implementation.
    merged_files: dict[str, str] = {}
    if impl_bundle.files:
        merged_files.update(impl_bundle.files)
    if bundle.files:
        for path, content in bundle.files.items():
            merged_files[f"proxy/{path}"] = content

    # Build merged bundle: address stays as original (proxy), source from impl.
    merged = SourceBundle(
        address=address,
        network=network,
        contract_name=impl_bundle.contract_name,
        compiler_version=impl_bundle.compiler_version,
        optimization_used=impl_bundle.optimization_used,
        runs=impl_bundle.runs,
        flattened_source=(
            f"// === IMPLEMENTATION ({impl_address}) ===\n{impl_source}"
            + (f"\n\n// === PROXY ({address}) ===\n{proxy_source}" if proxy_source else "")
        ) if not merged_files else None,
        files=merged_files,
        abi=impl_bundle.abi or bundle.abi,
        proxy=True,
        implementation=impl_address,
    )
    logger.info(
        "ingestion.proxy_merged",
        proxy=address,
        implementation=impl_address,
        impl_source_len=len(impl_source),
        proxy_source_len=len(proxy_source),
    )
    return merged
