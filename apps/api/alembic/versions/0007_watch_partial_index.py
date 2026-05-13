"""partial index for due_for_check

Revision ID: 0007_watch_idx
Revises: 0006_watch
Create Date: 2026-05-13

The watcher tick selects:
    WHERE (last_checked_at IS NULL OR last_checked_at < cutoff)
      AND error_count < 5
    ORDER BY last_checked_at ASC NULLS FIRST

A single-column btree on `last_checked_at` doesn't cover the
`error_count < 5` predicate, so Postgres falls back to a sequential
scan + sort across the whole table at every tick. A partial index
restricted to "still-active rows" makes the query index-only.

The index is on `last_checked_at` with NULLS FIRST so the planner can
walk the index in scan order; the partial predicate excludes burned-out
rows once and for all.
"""
from __future__ import annotations

from alembic import op

revision: str = "0007_watch_idx"
down_revision: str | None = "0006_watch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old single-column index — replaced by the partial form.
    op.execute("DROP INDEX IF EXISTS ix_watch_checked")
    op.execute(
        "CREATE INDEX ix_watch_due ON watched_contracts "
        "(last_checked_at NULLS FIRST) "
        "WHERE error_count < 5"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_watch_due")
    op.execute(
        "CREATE INDEX ix_watch_checked ON watched_contracts (last_checked_at)"
    )
