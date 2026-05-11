"""init scans and findings

Revision ID: 0001_init
Revises:
Create Date: 2026-05-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_init"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "scans",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("address", sa.String(128), nullable=False),
        sa.Column("network", sa.String(32), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=True),
        sa.Column("stage", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("tier", sa.String(16), nullable=True),
        sa.Column("report", postgresql.JSONB, nullable=True),
        sa.Column("engine_versions", postgresql.JSONB, nullable=True),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_scans_address", "scans", ["address"])
    op.create_index("ix_scans_network", "scans", ["network"])
    op.create_index("ix_scans_network_address", "scans", ["network", "address"])
    op.create_index("ix_scans_created_at", "scans", ["created_at"])

    op.create_table(
        "findings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("finding_key", sa.String(256), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("source_engine", sa.String(32), nullable=False),
        sa.Column("file", sa.String(512), nullable=True),
        sa.Column("line", sa.Integer, nullable=True),
        sa.Column("swc_id", sa.String(32), nullable=True),
        sa.Column("cwe_id", sa.String(32), nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.7"),
        sa.Column("dismissed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("dismissed_reason", sa.Text, nullable=True),
        sa.Column("poc_path", sa.String(512), nullable=True),
        sa.Column("poc_validated", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("extra", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_findings_scan_id", "findings", ["scan_id"])
    op.create_index("ix_findings_scan_severity", "findings", ["scan_id", "severity"])


def downgrade() -> None:
    op.drop_index("ix_findings_scan_severity", table_name="findings")
    op.drop_index("ix_findings_scan_id", table_name="findings")
    op.drop_table("findings")
    op.drop_index("ix_scans_created_at", table_name="scans")
    op.drop_index("ix_scans_network_address", table_name="scans")
    op.drop_index("ix_scans_network", table_name="scans")
    op.drop_index("ix_scans_address", table_name="scans")
    op.drop_table("scans")
