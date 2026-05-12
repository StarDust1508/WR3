"""users + scans.user_id

Revision ID: 0002_users
Revises: 0001_init
Create Date: 2026-05-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_users"
down_revision: str | None = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        # Multi-identity: any non-null subset means "logged in this way"
        sa.Column("telegram_user_id", sa.BigInteger, nullable=True),
        sa.Column("telegram_username", sa.String(64), nullable=True),
        sa.Column("wallet_address", sa.String(128), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(1024), nullable=True),
        # Pricing tier (free / hobby / team / pro) — defaults to "free"
        sa.Column("tier", sa.String(32), nullable=False, server_default="free"),
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
    # Uniqueness only when present (partial indexes — Postgres supports them).
    op.create_index(
        "ux_users_tg_id",
        "users",
        ["telegram_user_id"],
        unique=True,
        postgresql_where=sa.text("telegram_user_id IS NOT NULL"),
    )
    op.create_index(
        "ux_users_wallet",
        "users",
        ["wallet_address"],
        unique=True,
        postgresql_where=sa.text("wallet_address IS NOT NULL"),
    )
    op.create_index(
        "ux_users_email",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )

    op.add_column(
        "scans",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_scans_user_id", "scans", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_scans_user_id", table_name="scans")
    op.drop_column("scans", "user_id")
    op.drop_index("ux_users_email", table_name="users")
    op.drop_index("ux_users_wallet", table_name="users")
    op.drop_index("ux_users_tg_id", table_name="users")
    op.drop_table("users")
