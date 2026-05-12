"""watched_contracts table for continuous_monitoring

Revision ID: 0006_watch
Revises: 0005_incid
Create Date: 2026-05-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_watch"
down_revision: str | None = "0005_incid"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watched_contracts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("address", sa.String(128), nullable=False),
        sa.Column("network", sa.String(32), nullable=False),
        sa.Column("last_source_hash", sa.String(64), nullable=True),
        sa.Column("last_owner", sa.String(128), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "address", "network", name="ux_watch_user_addr_net"),
    )
    op.create_index("ix_watch_user", "watched_contracts", ["user_id"], unique=False)
    op.create_index(
        "ix_watch_checked", "watched_contracts", ["last_checked_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_watch_checked", table_name="watched_contracts")
    op.drop_index("ix_watch_user", table_name="watched_contracts")
    op.drop_table("watched_contracts")
