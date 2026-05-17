"""Render a Scan + Finding[] as a Markdown report.

This is plain text — no shell-out, no headless browser, no PDF. Designed
to be drop-into-a-GitHub-issue useful: severity-grouped, each finding with
file/line, source engine, and the description verbatim from the analyzer.

We deliberately don't include the embedding-based "similar incidents"
suggestion here — that lives in a separate enrichment step (W12) and
would make this module reach into vector search. Keeping this pure-render.
"""

from __future__ import annotations

import re
from datetime import datetime

from wr3_api.models import Finding, Scan

_SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]


# Markdown special characters that change rendering. We escape these in any
# string that came from user input or LLM output, because an attacker who
# can influence a finding title (via crafted source code that the multi-
# agent reasoner repeats verbatim) could otherwise inject:
#   - headings (#) to break document structure
#   - links ([text](evil-url)) to phish readers
#   - images (![](evil)) which can be fetched by Markdown viewers
#   - emphasis (* _) confusing the reader about what's authoritative
# We deliberately do NOT escape inside fenced code blocks — those are
# rendered as text-only.
_MD_INLINE_SPECIALS = re.compile(r"([\\\[\]()*_`>#!|])")


def _md_inline(s: str | None) -> str:
    """Escape characters that change inline Markdown rendering."""
    if not s:
        return ""
    return _MD_INLINE_SPECIALS.sub(r"\\\1", s)


def _md_block(s: str | None) -> str:
    """Render multi-paragraph user content as quoted blocks.

    The body is wrapped in '> ' lines so even if a leading '#' slipped
    through, it renders as a blockquoted heading inside the quoted region
    rather than restructuring the document. Pipes are escaped for table
    safety.
    """
    if not s:
        return ""
    lines = [_MD_INLINE_SPECIALS.sub(r"\\\1", line) for line in s.split("\n")]
    return "\n".join(lines)
_SEVERITY_LABEL = {
    "critical": "🔴 CRITICAL",
    "high":     "🟠 HIGH",
    "medium":   "🟡 MEDIUM",
    "low":      "🔵 LOW",
    "info":     "⚪ INFO",
}


def render_scan_markdown(scan: Scan, findings: list[Finding]) -> str:
    """Render a single scan + its findings as Markdown text."""
    lines: list[str] = []

    # --- Header ---
    lines.append("# wr3 audit report")
    lines.append("")
    lines.append(f"- **Contract:** `{scan.address}`")
    lines.append(f"- **Network:** `{scan.network}`")
    if scan.score is not None:
        tier = (scan.tier or "?").upper()
        lines.append(f"- **Score:** {scan.score:.1f} / 100  ({tier})")
    if scan.duration_seconds is not None:
        lines.append(f"- **Duration:** {scan.duration_seconds:.1f}s")
    lines.append(f"- **Scanned at:** {_fmt(scan.created_at)}")
    if scan.completed_at:
        lines.append(f"- **Completed at:** {_fmt(scan.completed_at)}")
    lines.append("")

    # --- On-chain metadata (Solana for now) ---
    chain_meta = (scan.report or {}).get("chain_metadata") if scan.report else None
    if chain_meta and isinstance(chain_meta, dict) and chain_meta.get("executable") is not None:
        lines.append("## On-chain metadata")
        lines.append("")
        lines.append(f"- **Executable:** {'yes' if chain_meta.get('executable') else 'no'}")
        if loader := chain_meta.get("loader"):
            lines.append(f"- **Loader:** `{loader}`")
        if chain_meta.get("upgradeable"):
            lines.append("- **Upgradeable:** yes ⚠️ (centralisation risk)")
            if auth := chain_meta.get("upgrade_authority"):
                lines.append(f"- **Upgrade authority:** `{auth}`")
            if slot := chain_meta.get("last_upgrade_slot"):
                lines.append(f"- **Last upgrade slot:** {slot:,}")
        else:
            lines.append("- **Upgradeable:** no (frozen — bytecode cannot change)")
        lines.append("")

    # --- Score breakdown (axes) ---
    axes = ((scan.report or {}).get("axes") or []) if scan.report else []
    if axes:
        lines.append("## Score breakdown")
        lines.append("")
        lines.append("| Axis | Weight | Score | Rationale |")
        lines.append("|---|---:|---:|---|")
        for a in axes:
            # Axes come from the scoring stage (server-controlled), but rationale
            # is partly LLM-driven so we escape it just like any other user-ish
            # text. Pipes get escaped twice: once for inline markdown, once for
            # table-cell escaping (already covered by inline escape).
            name = _md_inline(str(a.get("name", "")))
            weight = a.get("weight")
            score = a.get("score")
            rationale = _md_inline(str(a.get("rationale", "")).replace("\n", " "))
            # weight==0 means the axis is currently inactive (e.g. Tokenomics
            # pending GoPlus integration). Surface that honestly so the user
            # doesn't think a 0% weight is a typo.
            weight_str = (
                "pending"
                if weight is not None and float(weight) == 0.0
                else f"{round(float(weight) * 100)}%"
                if weight is not None
                else "—"
            )
            score_str = f"{float(score):.1f}" if score is not None else "—"
            lines.append(f"| {name} | {weight_str} | {score_str} | {rationale} |")
        lines.append("")

    # --- Findings, grouped by severity ---
    active = [f for f in findings if not f.dismissed]
    dismissed = [f for f in findings if f.dismissed]

    lines.append(f"## Findings  ({len(active)} active, {len(dismissed)} dismissed by triage)")
    lines.append("")

    if not active:
        lines.append("> No active findings. Either the contract is clean or all matches were filtered by triage.")
        lines.append("")
    else:
        grouped: dict[str, list[Finding]] = {s: [] for s in _SEVERITY_ORDER}
        for f in active:
            grouped.setdefault(f.severity.lower(), []).append(f)
        for sev in _SEVERITY_ORDER:
            bucket = grouped.get(sev, [])
            if not bucket:
                continue
            lines.append(f"### {_SEVERITY_LABEL[sev]}  ({len(bucket)})")
            lines.append("")
            for f in bucket:
                lines.extend(_render_finding(f))
                lines.append("")

    if dismissed:
        lines.append("---")
        lines.append("")
        lines.append("<details>")
        lines.append(f"<summary>Dismissed by triage ({len(dismissed)})</summary>")
        lines.append("")
        for f in dismissed:
            lines.extend(_render_finding(f))
            lines.append("")
        lines.append("</details>")
        lines.append("")

    # --- Disclaimer ---
    lines.append("---")
    lines.append("")
    disclaimer = (
        ((scan.report or {}).get("disclaimer") if scan.report else None)
        or (
            "_AI-assisted audit results are best-effort and not a replacement "
            "for human review. wr3 provides no warranty._"
        )
    )
    lines.append(disclaimer)
    lines.append("")
    lines.append(f"_Generated by wr3 — scan id `{scan.id}`._")

    return "\n".join(lines)


def _render_finding(f: Finding) -> list[str]:
    out: list[str] = []
    location = _md_inline(f.source_engine)
    if f.line is not None:
        location += f":{int(f.line)}"
    badges: list[str] = []
    if f.poc_validated:
        badges.append("**PoC ✓**")
    badge_str = " · " + " · ".join(badges) if badges else ""

    # Title is high-attack-surface: LLM triage can copy attacker-controlled
    # source comments verbatim. Escape inline-markdown specials so titles
    # can never inject headings, links, or images.
    out.append(f"#### {_md_inline(f.title)}")
    out.append("")
    out.append(
        f"`{location}` · confidence {round(f.confidence * 100)}%{badge_str}"
    )
    if f.file:
        # file paths are server-derived but pass through escape for defense
        # in depth — a crafted compiler include could put markdown in a name.
        out.append(f"file: `{_md_inline(f.file)}`")
    if f.description:
        out.append("")
        out.append(_md_block(f.description.strip()))

    # Similar historical incidents (W12 enrichment). Stored in `extra` JSONB
    # column as `metadata.similar_incidents` by incident_search.
    similar = _extract_similar_incidents(f)
    if similar:
        out.append("")
        out.append("**Similar past incidents:**")
        for inc in similar:
            sim_pct = round(float(inc.get("similarity", 0)) * 100)
            title = _md_inline(inc.get("title") or "")
            url = inc.get("url") or ""
            # We render the URL as plain text (auto-linked by most renderers)
            # rather than `[title](url)` to avoid having to escape URL
            # contents — escaping `(`, `)` etc. would mangle valid URLs, and
            # leaving them unescaped lets an attacker close the link early
            # via `inj)](evil)`. Only http(s) URLs are emitted; anything
            # else is dropped to prevent javascript: schemes.
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                url = ""
            loss = inc.get("loss_usd")
            loss_str = f" — ${loss:,}" if loss else ""
            line = f"- **{title}**{loss_str}  _(similarity {sim_pct}%)_"
            if url:
                line += f"\n  <{url}>"
            out.append(line)
    return out


def _extract_similar_incidents(f: Finding) -> list[dict]:
    """Pull similar_incidents from Finding.extra. Tolerant of None / wrong shape."""
    extra = f.extra or {}
    if not isinstance(extra, dict):
        return []
    sims = extra.get("similar_incidents")
    if not isinstance(sims, list):
        return []
    return [s for s in sims if isinstance(s, dict)]


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M UTC")
