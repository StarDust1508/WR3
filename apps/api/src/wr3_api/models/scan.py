from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wr3_api.models.base import Base, TimestampMixin


class Scan(Base, TimestampMixin):
    """One audit run per contract."""

    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    address: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    network: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Final report (only populated when stage == done)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    tier: Mapped[str | None] = mapped_column(String(16), nullable=True)
    report: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    engine_versions: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    findings: Mapped[list[Finding]] = relationship(
        back_populates="scan", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_scans_network_address", "network", "address"),
        Index("ix_scans_created_at", "created_at"),
    )


class Finding(Base, TimestampMixin):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    finding_key: Mapped[str] = mapped_column(String(256), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    source_engine: Mapped[str] = mapped_column(String(32), nullable=False)
    file: Mapped[str | None] = mapped_column(String(512), nullable=True)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    swc_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cwe_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dismissed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    poc_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    poc_validated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    scan: Mapped[Scan] = relationship(back_populates="findings")

    __table_args__ = (
        Index("ix_findings_scan_severity", "scan_id", "severity"),
    )
