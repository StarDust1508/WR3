"""incidents table with pgvector embedding

Revision ID: 0005_incid
Revises: 0004_subs
Create Date: 2026-05-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0005_incid"
down_revision: str | None = "0004_subs"
branch_labels = None
depends_on = None


# Must match wr3_api.models.incident.EMBEDDING_DIM.
_EMBEDDING_DIM = 1536


def upgrade() -> None:
    # pgvector must exist (installed by hand in 0001 era). Ensure it just
    # in case this migration runs on a fresh box where vector wasn't pre-
    # installed.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "incidents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("summary", sa.Text, nullable=False, server_default=""),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column(
            "extra_urls",
            postgresql.ARRAY(sa.String(1024)),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column(
            "extra_sources",
            postgresql.ARRAY(sa.String(32)),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("loss_usd", sa.BigInteger, nullable=True),
        sa.Column("embedding", Vector(_EMBEDDING_DIM), nullable=True),
        sa.Column(
            "raw",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
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
    )
    op.create_index(
        "ix_incidents_published_at", "incidents", ["published_at"], unique=False
    )
    op.create_index("ix_incidents_source", "incidents", ["source"], unique=False)
    op.create_index("ix_incidents_url", "incidents", ["url"], unique=False)

    # IVFFlat index for fast cosine similarity search. With <1000 rows the
    # planner falls back to seq scan, which is fine; the index pays off at
    # scale. lists=100 is a reasonable default for up to ~1M rows.
    op.execute(
        "CREATE INDEX ix_incidents_embedding_cosine "
        "ON incidents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_incidents_embedding_cosine")
    op.drop_index("ix_incidents_url", table_name="incidents")
    op.drop_index("ix_incidents_source", table_name="incidents")
    op.drop_index("ix_incidents_published_at", table_name="incidents")
    op.drop_table("incidents")
