"""Etherscan contract-creation metadata for the On-chain Behavior axis.

The 4th scoring axis from TZ §8.1 was "On-chain Behavior" — TVL trend,
swap volume, anomaly score, age. The simplest, free, free-tier signal
of all those is **contract age**. A contract deployed 5 years ago has
proven not-rugged-yet; one deployed yesterday is in the highest-risk
band for fly-by-night scams.

We pull creation block + timestamp from Etherscan V2's
`getcontractcreation` action — free tier, same key as the source fetcher.

Other on-chain signals (TVL trend via DefiLlama, swap volume) need
per-protocol mapping that's loose at the contract-address level.
Wireable as Phase-2 enrichment without changing this module's contract.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = structlog.get_logger()


_ETHERSCAN_V2 = "https://api.etherscan.io/v2/api"

# Same chain-id map the source fetcher uses. Solana is intentionally
# absent — Etherscan doesn't cover it; Solana's on-chain age signal
# would come from the slot in `solana_metadata.SolanaMetadataFetcher`
# instead (already implemented).
_CHAIN_IDS = {
    "ethereum": 1,
    "bsc": 56,
    "polygon": 137,
    "base": 8453,
    "arbitrum": 42161,
}


@dataclass
class ContractCreation:
    """Subset of getcontractcreation response we care about."""

    address: str
    network: str
    creator: str
    tx_hash: str
    block_number: int
    timestamp: datetime
    age_days: int

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "network": self.network,
            "creator": self.creator,
            "block_number": self.block_number,
            "deployed_at": self.timestamp.isoformat(),
            "age_days": self.age_days,
        }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
async def fetch_contract_creation(
    *, address: str, network: str, timeout: float = 10.0
) -> ContractCreation | None:
    """Return the creation tx + timestamp for an EVM contract.

    Returns None when:
        - network isn't an Etherscan-supported chain
        - the address doesn't have a creation record (EOA, not a contract)
        - Etherscan rejects (rate limit, key not configured)
    """
    chain_id = _CHAIN_IDS.get(network)
    if chain_id is None or not address.startswith("0x"):
        return None

    api_key = os.getenv("ETHERSCAN_API_KEY", "").strip()
    if not api_key:
        logger.info("etherscan_meta.no_api_key")
        return None

    params = {
        "chainid": chain_id,
        "module": "contract",
        "action": "getcontractcreation",
        "contractaddresses": address.lower(),
        "apikey": api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(_ETHERSCAN_V2, params=params)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        logger.warning("etherscan_meta.http_error", error=str(e))
        return None

    # Etherscan returns `{"status":"1", "result":[...]}` on hit,
    # `{"status":"0", "result":"..."}` (string) on miss/error.
    if data.get("status") != "1":
        logger.info(
            "etherscan_meta.empty", message=data.get("message"), result=data.get("result")
        )
        return None
    rows = data.get("result")
    if not isinstance(rows, list) or not rows:
        return None
    record = rows[0]
    try:
        timestamp = datetime.fromtimestamp(int(record["timestamp"]), tz=UTC)
        block_number = int(record["blockNumber"])
    except (KeyError, ValueError, TypeError) as e:
        logger.warning("etherscan_meta.bad_shape", error=str(e))
        return None

    age_days = max(0, (datetime.now(UTC) - timestamp).days)

    return ContractCreation(
        address=address,
        network=network,
        creator=record.get("contractCreator", ""),
        tx_hash=record.get("txHash", ""),
        block_number=block_number,
        timestamp=timestamp,
        age_days=age_days,
    )


def compute_onchain_behavior_score(
    creation: ContractCreation,
) -> tuple[float, str]:
    """Age-based score for the On-chain Behavior axis.

    Calibrated against historical rug data: fly-by-night scams typically
    rug within the first 30 days. Survival past 90 days is a strong
    "not-instant-scam" signal. Past 1 year, the contract has been
    actively used and the team hasn't pulled — high confidence.

    Bands:
        > 365 d   = 100  (mature, proven)
        90-365 d  = 80   (established)
        30-90 d   = 60   (young — moderate risk)
        7-30 d    = 35   (very young — high risk)
        < 7 d     = 15   (brand new — highest risk band before fraud signal)
    """
    age = creation.age_days
    if age > 365:
        return 100.0, f"On-chain: контракт развёрнут {age // 30} мес. назад (зрелый)"
    if age > 90:
        return 80.0, f"On-chain: {age} дней с деплоя (устоявшийся)"
    if age > 30:
        return 60.0, f"On-chain: {age} дней с деплоя (молодой, умеренный риск)"
    if age > 7:
        return 35.0, f"On-chain: {age} дней с деплоя (свежий, высокий риск)"
    return 15.0, f"On-chain: всего {age} дней с деплоя — наивысший риск"
