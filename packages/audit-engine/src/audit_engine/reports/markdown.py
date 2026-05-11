from __future__ import annotations

from audit_engine.types import AuditReport


def render_markdown(report: AuditReport) -> str:
    lines: list[str] = [
        "# wr3 Audit Report",
        "",
        f"- **Contract:** `{report.address}`",
        f"- **Network:** {report.network}",
        f"- **Score:** **{report.score}/100** ({report.tier})",
        "",
        "## Score breakdown",
        "",
        "| Axis | Weight | Score | Rationale |",
        "|---|---:|---:|---|",
    ]
    for a in report.axes:
        lines.append(f"| {a.name} | {a.weight:.0%} | {a.score:.1f} | {a.rationale} |")

    lines += ["", "## Findings", ""]
    if not report.findings:
        lines.append("_No active findings._")
    else:
        lines.append("| # | Severity | Engine | Title | Location |")
        lines.append("|---:|---|---|---|---|")
        for i, f in enumerate(report.findings, 1):
            loc = f"{f.file or '-'}:{f.line or '-'}"
            lines.append(f"| {i} | {f.severity.value} | {f.source_engine} | {f.title} | {loc} |")

    lines += [
        "",
        "---",
        "",
        f"_{report.disclaimer}_",
    ]
    return "\n".join(lines)
