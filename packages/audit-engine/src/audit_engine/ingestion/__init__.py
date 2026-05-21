"""Verified source fetcher for Etherscan-family explorers and Solana.

Endpoint design (per TZ.md §4.1 Stage 1):
    fetch_source(address, network) -> SourceBundle | None

SourceBundle carries:
    - flattened source code OR multi-file dict
    - compiler version
    - optimization settings
    - contract name
"""

from audit_engine.ingestion.fetcher import (
    SourceBundle,
    SourceFetcher,
    fetch_source,
    fetch_source_with_implementation,
)

__all__ = ["SourceBundle", "SourceFetcher", "fetch_source", "fetch_source_with_implementation"]
