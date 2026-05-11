"""DB persistence for scans and findings."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from wr3_api.db import SessionFactory
from wr3_api.models import Finding as FindingRow
from wr3_api.models import Scan as ScanRow


async def create_scan(*, address: str, network: str) -> uuid.UUID:
    """Insert a Scan row in `queued` state and return its id."""
    async with SessionFactory() as session:
        row = ScanRow(address=address, network=network, stage="queued", progress=0)
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row.id


async def update_progress(
    *,
    scan_id: uuid.UUID,
    stage: str,
    progress: int,
    error_message: str | None = None,
) -> None:
    async with SessionFactory() as session:
        row = await session.get(ScanRow, scan_id)
        if row is None:
            return
        row.stage = stage
        row.progress = progress
        if error_message is not None:
            row.error_message = error_message
        await session.commit()


async def finalize_scan(
    *,
    scan_id: uuid.UUID,
    report_dict: dict[str, Any],
    duration_seconds: float,
) -> None:
    async with SessionFactory() as session:
        row = await session.get(ScanRow, scan_id)
        if row is None:
            return
        row.stage = "done"
        row.progress = 100
        row.score = float(report_dict.get("score") or 0.0)
        row.tier = report_dict.get("tier")
        row.report = report_dict
        row.engine_versions = report_dict.get("engine_versions") or {}
        row.duration_seconds = duration_seconds
        row.completed_at = datetime.now(UTC)

        # Persist findings as separate rows for indexing / filtering
        for f in report_dict.get("findings", []):
            session.add(
                FindingRow(
                    scan_id=scan_id,
                    finding_key=str(f.get("id", "")),
                    title=f.get("title", "")[:512],
                    description=f.get("description", "") or "",
                    severity=f.get("severity", "info"),
                    source_engine=f.get("source_engine", "unknown"),
                    file=f.get("file"),
                    line=f.get("line"),
                    swc_id=f.get("swc_id"),
                    cwe_id=f.get("cwe_id"),
                    confidence=float(f.get("confidence", 0.7)),
                    dismissed=bool(f.get("dismissed", False)),
                    dismissed_reason=f.get("dismissed_reason"),
                    poc_path=f.get("poc_path"),
                    poc_validated=bool(f.get("poc_validated", False)),
                    extra=f.get("metadata"),
                )
            )
        await session.commit()


async def get_scan(scan_id: uuid.UUID) -> ScanRow | None:
    async with SessionFactory() as session:
        return await session.get(ScanRow, scan_id)


async def get_scan_with_findings(scan_id: uuid.UUID) -> tuple[ScanRow, list[FindingRow]] | None:
    async with SessionFactory() as session:
        row = await session.get(ScanRow, scan_id)
        if row is None:
            return None
        result = await session.execute(
            select(FindingRow).where(FindingRow.scan_id == scan_id).order_by(FindingRow.severity)
        )
        findings = list(result.scalars().all())
        return row, findings


async def recent_scans(*, limit: int = 20) -> list[ScanRow]:
    async with SessionFactory() as session:
        result = await session.execute(
            select(ScanRow).order_by(ScanRow.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())
