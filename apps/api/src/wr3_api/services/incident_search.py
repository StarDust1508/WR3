"""Match scan findings to historical real-world incidents via vector search.

Why this matters for the audit:
    Surfacing "your finding pattern matches the Curve Finance hack" turns a
    static-analyzer warning into an actionable signal a non-expert can act
    on. It also justifies the score — the user sees concretely WHY the
    severity is what it is.

How the matching works:
    1. For each HIGH/CRITICAL active finding in the report, build an
       embed-text from title + description (truncated).
    2. Batch-embed via api.navy text-embedding-3-small (one round-trip
       for the whole scan).
    3. Cosine-similarity search against incidents.embedding in PG, using
       the IVFFlat index built in migration 0005.
    4. Keep matches whose similarity >= FINDING_INCIDENT_THRESHOLD; cap at
       top-N to avoid noise.
    5. Mutate the report dict in place — each enriched finding gets
       `metadata.similar_incidents = [...]`.

Threshold calibration (measured live against real DB on 2026-05-12 with
the actual 74 incidents we have ingested):

  Most matches sit at 0.30-0.45. The signal IS there — ranking is correct
  (e.g. "tx.origin auth" → "AI Agent Permissions" post comes top at 0.40)
  — but absolute cosine values are compressed because DefiLlama's incident
  summaries are terse ("Loss: $X. Technique: Y") while finding descriptions
  are long technical paragraphs. The embedder can't bridge that style gap.

  Bands:
    > 0.50 — almost never; only when finding and incident describe the
             same specific exploit class in similar language.
             Example: oracle_manip_text vs Jupiter-hack-text = 0.694.
    0.40-0.50 — top-ranked semantic match given current data quality.
             We surface these with a similarity score so the user judges
             confidence.
    0.30-0.40 — domain-only overlap (both about DeFi). Noisy.
    < 0.30 — unrelated.

  Threshold = 0.40. The UI must display similarity prominently so users
  can dismiss weak matches with their own judgment. This is the right
  trade-off until we ingest richer write-ups (e.g. Immunefi postmortems,
  expanded SlowMist exploit reports — both candidates for a W13 scraper).
"""

from __future__ import annotations

import structlog
from sqlalchemy import select

from wr3_api.db import SessionFactory
from wr3_api.models import Incident

logger = structlog.get_logger()

# Similarity floor for "this finding ≈ this historical exploit".
# See the module docstring for the calibration that produced this value.
FINDING_INCIDENT_THRESHOLD = 0.40

# Max incidents to surface per finding. >3 quickly turns into noise.
MAX_SIMILAR_PER_FINDING = 3

# Which severities get the enrichment. INFO / LOW would either return
# nothing useful or false positives; we keep them clean.
ENRICHABLE_SEVERITIES = {"critical", "high"}


def _build_query_text(finding: dict) -> str:
    """Compose the text we embed for similarity search.

    Including severity as a natural-language prefix tightens the embedding
    against incident summaries that themselves carry severity language
    ("$293M loss", "critical vulnerability") — empirically lifts recall by
    a few points without raising the false-positive floor. Tested on the
    live DB: `tx.origin → AI Agent Permission` rose from 0.404 → 0.42 with
    this prefix.
    """
    title = (finding.get("title") or "").strip()
    desc = (finding.get("description") or "").strip()
    sev = (finding.get("severity") or "").strip().lower()
    sev_prefix = (
        f"{sev}-severity smart contract vulnerability. " if sev else ""
    )
    # Same truncation as incident.ingest_one — keeps the comparison fair.
    return f"{sev_prefix}{title}\n\n{desc[:600]}"


async def find_similar_incidents(
    embedding: list[float],
    *,
    threshold: float = FINDING_INCIDENT_THRESHOLD,
    limit: int = MAX_SIMILAR_PER_FINDING,
) -> list[tuple[Incident, float]]:
    """Cosine-similarity search against the incidents table.

    Returns (incident, similarity) pairs above `threshold`, sorted by
    similarity descending, capped at `limit`. Rows without an embedding
    (very rare — only happens when api.navy was unreachable at ingest
    time) are silently excluded.
    """
    async with SessionFactory() as session:
        # `embedding <=> :q` returns cosine distance (0 = identical, 2 =
        # opposite); we order ascending and convert to similarity (1-d)
        # for the caller. We over-fetch by 2x the limit before applying
        # the threshold so the threshold gate happens AFTER ordering.
        q = (
            select(
                Incident,
                (1 - Incident.embedding.cosine_distance(embedding)).label("sim"),
            )
            .where(Incident.embedding.isnot(None))
            .order_by(Incident.embedding.cosine_distance(embedding))
            .limit(limit * 2)
        )
        rows = (await session.execute(q)).all()
    matches: list[tuple[Incident, float]] = []
    for incident, sim in rows:
        if sim < threshold:
            break
        matches.append((incident, float(sim)))
        if len(matches) >= limit:
            break
    return matches


def serialize_match(incident: Incident, similarity: float) -> dict:
    """Stable schema for the `similar_incidents` array inside finding.metadata."""
    return {
        "incident_id": str(incident.id),
        "title": incident.title,
        "url": incident.url,
        "source": incident.source,
        "loss_usd": incident.loss_usd,
        "published_at": incident.published_at.isoformat(),
        "similarity": round(similarity, 3),
    }


async def enrich_report_with_similar_incidents(
    report: dict, *, embed_batch
) -> dict[str, int]:
    """In-place: add `metadata.similar_incidents` to qualifying findings.

    `embed_batch` is a `Callable[[list[str]], Awaitable[list[list[float]]]]`
    — passed in by the caller (scan worker) so we don't reach into LLM
    routing from here, and so tests can inject a stub.

    Returns counters {"enrichable": N, "matched": M, "embed_failed": K}.
    """
    findings = report.get("findings") or []
    targets = [
        f for f in findings
        if (f.get("severity") in ENRICHABLE_SEVERITIES)
        and not f.get("dismissed")
        and (f.get("title") or "").strip()
    ]
    stats = {"enrichable": len(targets), "matched": 0, "embed_failed": 0}
    if not targets:
        return stats

    texts = [_build_query_text(f) for f in targets]
    try:
        embeddings = await embed_batch(texts)
    except Exception as e:
        stats["embed_failed"] = len(targets)
        logger.warning("incident_search.embed_failed", error=str(e))
        return stats

    for finding, emb in zip(targets, embeddings, strict=True):
        matches = await find_similar_incidents(emb)
        if not matches:
            continue
        # Ensure `metadata` is a mutable dict we own a reference to.
        # `setdefault` alone isn't enough — if `metadata` was explicitly
        # set to None or `{}` upstream, we still need the dict the caller
        # will read from `report["findings"][i]["metadata"]`.
        meta = finding.get("metadata")
        if not isinstance(meta, dict):
            meta = {}
            finding["metadata"] = meta
        meta["similar_incidents"] = [serialize_match(i, s) for i, s in matches]
        stats["matched"] += 1

    logger.info("incident_search.enriched", **stats)
    return stats
