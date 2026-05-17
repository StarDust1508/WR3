"""Team / KYC axis enrichment — the 5th and final scoring axis.

Signals used:
    1. MetaMask Eth Phishing Detect list — checks whether the deployer
       address appears in the community-maintained blacklist of known
       scammers / phishers. Presence = instant score floor.
    2. Source verification status — is the contract verified on Etherscan?
       Already known from the source ingestion stage (if we got source
       from explorer, it's verified). Unverified = anonymity signal.
    3. Deployer age — if we have the deployer from etherscan_meta, check
       how many txns they've done. A brand-new wallet with 1 tx
       (just deploying this contract) is higher risk than a wallet
       with years of history.

The MetaMask phishing list is fetched from GitHub raw content — a flat
JSON array of known-bad domains/addresses. We cache it for 1 hour to
avoid hammering GitHub on every scan.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = structlog.get_logger()

_PHISHING_LIST_URL = (
    "https://raw.githubusercontent.com/MetaMask/eth-phishing-detect/"
    "master/src/config.json"
)

_phishing_cache: _PhishingCache | None = None
_CACHE_TTL = 3600

_team_kyc_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _team_kyc_client
    if _team_kyc_client is None:
        _team_kyc_client = httpx.AsyncClient(timeout=30.0)
    return _team_kyc_client


@dataclass
class _PhishingCache:
    blacklist: set[str]
    fetched_at: float


@dataclass
class TeamKYCSignals:
    """Collected signals for the Team/KYC scoring axis."""

    deployer_on_phishing_list: bool
    deployer_address: str | None
    source_verified: bool
    deployer_tx_count: int | None

    def to_dict(self) -> dict:
        return {
            "deployer_on_phishing_list": self.deployer_on_phishing_list,
            "deployer_address": self.deployer_address,
            "source_verified": self.source_verified,
            "deployer_tx_count": self.deployer_tx_count,
        }


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
async def _fetch_phishing_list() -> set[str]:
    """Fetch MetaMask's phishing blacklist (addresses + domains).

    The config.json has structure: {"blacklist": [...], "whitelist": [...], ...}
    We extract blacklist entries that look like Ethereum addresses (0x...).
    """
    global _phishing_cache
    now = time.monotonic()
    if _phishing_cache is not None and (now - _phishing_cache.fetched_at) < _CACHE_TTL:
        return _phishing_cache.blacklist

    client = _get_client()
    r = await client.get(_PHISHING_LIST_URL)
    r.raise_for_status()
    data = r.json()

    addresses: set[str] = set()
    for entry in data.get("blacklist", []):
        if isinstance(entry, str):
            lower = entry.lower().strip()
            if lower.startswith("0x") and len(lower) == 42:
                addresses.add(lower)

    _phishing_cache = _PhishingCache(blacklist=addresses, fetched_at=now)
    logger.info("team_kyc.phishing_list_loaded", count=len(addresses))
    return addresses


async def fetch_team_kyc_signals(
    *,
    address: str,
    network: str,
    deployer: str | None = None,
    source_verified: bool = True,
) -> TeamKYCSignals | None:
    """Gather Team/KYC signals for the given contract.

    Parameters:
        address: the audited contract address
        network: network name
        deployer: deployer address (from etherscan_meta.ContractCreation)
        source_verified: whether source code was fetched from explorer
    """
    if network == "solana":
        return None

    deployer_on_list = False
    deployer_tx_count: int | None = None

    if deployer:
        try:
            blacklist = await _fetch_phishing_list()
            deployer_on_list = deployer.lower() in blacklist
        except Exception as e:
            logger.warning("team_kyc.phishing_check_failed", error=str(e))

        deployer_tx_count = await _fetch_deployer_tx_count(
            deployer=deployer, network=network
        )

    return TeamKYCSignals(
        deployer_on_phishing_list=deployer_on_list,
        deployer_address=deployer,
        source_verified=source_verified,
        deployer_tx_count=deployer_tx_count,
    )


async def _fetch_deployer_tx_count(*, deployer: str, network: str) -> int | None:
    """Get deployer's transaction count from Etherscan V2.

    A high nonce (many transactions) implies an established entity —
    not a burner wallet created just for this deploy.
    """
    import os

    api_key = os.getenv("ETHERSCAN_API_KEY", "").strip()
    if not api_key:
        return None

    chain_ids = {
        "ethereum": 1,
        "bsc": 56,
        "polygon": 137,
        "base": 8453,
        "arbitrum": 42161,
    }
    chain_id = chain_ids.get(network)
    if chain_id is None:
        return None

    params = {
        "chainid": chain_id,
        "module": "proxy",
        "action": "eth_getTransactionCount",
        "address": deployer.lower(),
        "tag": "latest",
        "apikey": api_key,
    }
    try:
        client = _get_client()
        r = await client.get("https://api.etherscan.io/v2/api", params=params)
        r.raise_for_status()
        data = r.json()
        hex_count = data.get("result", "0x0")
        if isinstance(hex_count, str) and hex_count.startswith("0x"):
            return int(hex_count, 16)
    except Exception as e:
        logger.warning("team_kyc.tx_count_failed", error=str(e))

    return None


def compute_team_kyc_score(signals: TeamKYCSignals) -> tuple[float, str]:
    """Convert TeamKYCSignals into a 0-100 score + rationale.

    Calibration:
        Deployer on phishing list     → floor to 0 (terminal)
        Source not verified            → -25 (hides intent)
        Deployer tx_count < 5          → -20 (burner wallet)
        Deployer tx_count 5-20         → -10 (low activity)
        Deployer tx_count 20-100       → -0  (moderate)
        Deployer tx_count > 100        → +0  (established)
        No deployer data               → -15 (can't verify)
    """
    if signals.deployer_on_phishing_list:
        return 0.0, "Team/KYC: деплоер в списке фишинга MetaMask — максимальный риск"

    score = 100.0
    parts: list[str] = []

    def deduct(amount: float, reason: str) -> None:
        nonlocal score
        score -= amount
        parts.append(reason)

    if not signals.source_verified:
        deduct(25, "исходный код не верифицирован")

    if signals.deployer_address is None:
        deduct(15, "деплоер неизвестен")
    elif signals.deployer_tx_count is not None:
        tc = signals.deployer_tx_count
        if tc < 5:
            deduct(20, f"деплоер имеет только {tc} транзакций (burner wallet)")
        elif tc < 20:
            deduct(10, f"деплоер имеет {tc} транзакций (низкая активность)")
    elif signals.deployer_tx_count is None and signals.deployer_address:
        deduct(10, "не удалось проверить историю деплоера")

    score = max(0.0, min(100.0, score))
    rationale = (
        "Team/KYC: " + "; ".join(parts)
        if parts
        else "Team/KYC: верифицированный контракт, опытный деплоер"
    )
    return round(score, 1), rationale
