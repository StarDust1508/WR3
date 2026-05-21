"""Network-aware confidence adjustment for findings.

Different networks have fundamentally different risk profiles:
- Ethereum mainnet: MEV is king, sandwich attacks dominate, gas costs limit some exploits
- L2s (Arbitrum, Base, Optimism): Sequencer centralization risk, lower gas enables more complex attacks
- BSC: Higher rug-pull rate, many unaudited forks, flash loan attacks common

This module post-processes findings to adjust confidence based on network context.
"""

from __future__ import annotations

from audit_engine.types import Finding, Network, Severity

# Network-specific confidence multipliers for certain rule categories
NETWORK_ADJUSTMENTS: dict[str, dict[str, float]] = {
    "ethereum": {
        # MEV/sandwich very real on mainnet
        "sandwich-vulnerable-swap": 1.3,
        "missing-slippage-protection": 1.3,
        "swap-missing-deadline": 1.3,
        "flash-loan-callback": 1.2,
        "oracle-spot-price-dependency": 1.2,
        # Gas costs make some attacks impractical
        "unbounded-loop": 0.8,  # gas limit already protects somewhat
    },
    "base": {
        # L2 sequencer risk
        "timestamp-dependence": 1.3,  # sequencer controls timestamps
        "chainlink-stale-price": 1.4,  # sequencer downtime breaks oracles
        # Lower gas = more complex attacks viable
        "unbounded-loop": 1.2,
        "flash-loan-callback": 1.2,
    },
    "arbitrum": {
        "timestamp-dependence": 1.3,
        "chainlink-stale-price": 1.4,
        "unbounded-loop": 1.2,
        "flash-loan-callback": 1.2,
    },
    "bsc": {
        # BSC: rug pulls, unaudited forks
        "unsafe-ownership-transfer": 1.3,
        "unprotected-initializer": 1.2,
        "centralization-single-admin": 1.4,
        "missing-event-emission": 1.2,  # makes monitoring harder
        "flash-loan-callback": 1.3,
    },
}

# L2-specific findings that should be ADDED when scanning L2 contracts
L2_NETWORKS = {"base", "arbitrum", "optimism"}


def adjust_confidence_for_network(
    findings: list[Finding],
    network: Network,
) -> list[Finding]:
    """Adjust finding confidence based on target network characteristics."""
    adjustments = NETWORK_ADJUSTMENTS.get(network, {})
    if not adjustments:
        return findings

    adjusted: list[Finding] = []
    for f in findings:
        # Extract rule_id from finding id (format: "engine:rule_id:line")
        parts = f.id.split(":")
        rule_id = parts[1] if len(parts) >= 2 else ""

        multiplier = adjustments.get(rule_id, 1.0)
        if multiplier != 1.0:
            new_confidence = min(1.0, max(0.0, f.confidence * multiplier))
            adjusted.append(f.model_copy(update={
                "confidence": round(new_confidence, 2),
                "metadata": {
                    **f.metadata,
                    "network_adjustment": {
                        "network": network,
                        "original_confidence": f.confidence,
                        "multiplier": multiplier,
                    },
                },
            }))
        else:
            adjusted.append(f)

    return adjusted


def generate_l2_warnings(network: Network) -> list[Finding]:
    """Generate L2-specific informational findings."""
    if network not in L2_NETWORKS:
        return []

    warnings = []
    warnings.append(Finding(
        id="network-context:l2-sequencer-risk:0",
        title="L2 sequencer centralization — timestamp and ordering risk",
        description=(
            f"This contract is deployed on {network}, an L2 with a centralized "
            "sequencer. The sequencer controls transaction ordering and block "
            "timestamps. This means: (1) block.timestamp is sequencer-controlled "
            "with wider manipulation range than L1, (2) MEV extraction patterns "
            "differ from mainnet, (3) sequencer downtime can break time-dependent "
            "logic and oracle staleness checks. If this contract uses Chainlink, "
            "add a sequencer uptime feed check."
        ),
        severity=Severity.INFO,
        source_engine="network-context",
        confidence=0.9,
    ))

    return warnings
