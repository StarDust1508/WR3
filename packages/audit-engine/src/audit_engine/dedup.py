"""Cross-engine finding deduplication.

When multiple static analyzers report the same vulnerability at the same
location, we merge them into a single finding with richer metadata
rather than showing N duplicate cards.

Merge strategy:
1. Group findings by (approximate_line, severity_bucket, semantic_similarity)
2. Within each group, keep the highest-confidence finding as primary
3. Add other engines to metadata.engines list
4. Merge descriptions if they add unique information
5. Boost confidence when multiple engines agree (more signals = more likely real)
"""

from __future__ import annotations

from audit_engine.types import Finding, Severity

# How close lines must be to be considered "same location"
LINE_PROXIMITY = 5

# Severity grouping for dedup (these severities are considered "same bucket")
SEVERITY_GROUPS = {
    Severity.CRITICAL: {Severity.CRITICAL, Severity.HIGH},
    Severity.HIGH: {Severity.CRITICAL, Severity.HIGH},
    Severity.MEDIUM: {Severity.MEDIUM},
    Severity.LOW: {Severity.LOW, Severity.INFO},
    Severity.INFO: {Severity.LOW, Severity.INFO},
}

# Keywords that indicate the same class of vulnerability
SEMANTIC_CLUSTERS: list[set[str]] = [
    {"reentrancy", "reentrant", "re-entrancy", "re-entrant", "callback"},
    {"overflow", "underflow", "arithmetic", "truncat", "downcast"},
    {"access control", "authorization", "permission", "onlyowner", "admin", "privilege"},
    {"oracle", "price", "manipulation", "flash loan", "spot price", "twap"},
    {"slippage", "sandwich", "mev", "frontrun", "front-run", "deadline"},
    {"initializ", "constructor", "proxy", "upgradeable", "uups"},
    {"selfdestruct", "suicide", "destroy"},
    {"delegatecall", "delegate", "proxy call"},
    {"ecrecover", "signature", "ecdsa", "replay", "nonce", "permit"},
    {"erc20", "transfer", "approve", "allowance", "safeTransfer"},
    {"erc721", "erc1155", "nft", "safe mint", "safetransfer"},
    {"unchecked", "return value", "low-level call"},
    {"timestamp", "block.number", "randomness"},
    {"loop", "gas", "dos", "denial", "unbounded"},
    {"storage", "collision", "slot", "layout"},
]


def _semantic_cluster(text: str) -> int | None:
    """Return cluster index if the text matches a known vulnerability cluster."""
    lower = text.lower()
    for i, cluster in enumerate(SEMANTIC_CLUSTERS):
        if any(kw in lower for kw in cluster):
            return i
    return None


def _is_same_issue(a: Finding, b: Finding) -> bool:
    """Heuristic: do two findings describe the same underlying issue?"""
    # Same engine = never dedup (engine already handles internal dedup)
    if a.source_engine == b.source_engine:
        return False

    # Line proximity check (if both have lines)
    if a.line is not None and b.line is not None:
        if abs(a.line - b.line) > LINE_PROXIMITY:
            return False
    elif a.line is not None or b.line is not None:
        # One has a line, other doesn't — can still match
        pass

    # Severity bucket check
    a_bucket = SEVERITY_GROUPS.get(a.severity, {a.severity})
    if b.severity not in a_bucket:
        return False

    # Semantic similarity: check if both titles/descriptions fall in the same cluster
    a_cluster = _semantic_cluster(a.title + " " + a.description)
    b_cluster = _semantic_cluster(b.title + " " + b.description)

    if a_cluster is not None and b_cluster is not None:
        return a_cluster == b_cluster

    # Title overlap as fallback
    a_words = set(a.title.lower().split())
    b_words = set(b.title.lower().split())
    # Remove common stop words
    stop = {"a", "an", "the", "in", "on", "of", "for", "to", "is", "with", "without", "—", "-", "and", "or"}
    a_words -= stop
    b_words -= stop
    if len(a_words) < 2 or len(b_words) < 2:
        return False
    overlap = len(a_words & b_words) / min(len(a_words), len(b_words))
    return overlap >= 0.5


def _merge_findings(group: list[Finding]) -> Finding:
    """Merge a group of findings about the same issue into one."""
    # Sort by confidence desc, then by description length desc (richer = better)
    group.sort(key=lambda f: (-f.confidence, -len(f.description)))
    primary = group[0]

    # Collect all engine names
    all_engines = list(dict.fromkeys(f.source_engine for f in group))

    # Collect all unique description sentences for the "confirms" metadata
    confirms = []
    for f in group[1:]:
        if f.description and f.description != primary.description:
            confirms.append(f.description[:600])

    # Confidence boost: multiple engines agreeing increases confidence
    # Each additional engine adds up to 0.1 confidence
    boost = min(0.2, (len(group) - 1) * 0.1)
    new_confidence = min(1.0, primary.confidence + boost)

    # Take highest severity from the group
    sev_order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]
    highest_sev = min(group, key=lambda f: sev_order.index(f.severity)).severity

    # Merge metadata
    merged_metadata = dict(primary.metadata)
    merged_metadata["engines"] = all_engines
    merged_metadata["dedup_merged_count"] = len(group)
    if confirms:
        merged_metadata["confirms"] = confirms
    # Collect line numbers from all engines
    lines = [f.line for f in group if f.line is not None]
    if lines:
        merged_metadata["locations"] = sorted(set(lines))

    return primary.model_copy(update={
        "severity": highest_sev,
        "confidence": round(new_confidence, 2),
        "metadata": merged_metadata,
    })


def deduplicate_findings(findings: list[Finding]) -> list[Finding]:
    """Merge findings from different engines that describe the same issue.

    Returns a new list with duplicates merged. Original list is not modified.
    """
    if len(findings) <= 1:
        return list(findings)

    # Build groups using union-find approach
    n = len(findings)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Compare all pairs (O(n^2) but n is typically < 200)
    for i in range(n):
        for j in range(i + 1, n):
            if _is_same_issue(findings[i], findings[j]):
                union(i, j)

    # Group findings
    groups: dict[int, list[Finding]] = {}
    for i, f in enumerate(findings):
        root = find(i)
        groups.setdefault(root, []).append(f)

    # Merge each group
    result = []
    for group in groups.values():
        if len(group) == 1:
            # Single finding — ensure it has engines metadata
            f = group[0]
            if "engines" not in f.metadata:
                f = f.model_copy(update={
                    "metadata": {**f.metadata, "engines": [f.source_engine]},
                })
            result.append(f)
        else:
            result.append(_merge_findings(group))

    # Sort by severity (most severe first), then by line
    sev_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3, Severity.INFO: 4}
    result.sort(key=lambda f: (sev_order.get(f.severity, 5), f.line or 9999))

    return result
