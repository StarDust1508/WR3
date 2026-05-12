"""user.preferences for owner toggles

Revision ID: 0003_prefs
Revises: 0002_users
Create Date: 2026-05-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_prefs"
down_revision: str | None = "0002_users"
branch_labels = None
depends_on = None


# Default preferences for a freshly created user.
# Stored as JSONB so we can evolve without migrations for each new toggle.
_DEFAULT_PREFS = {
    # When True, pipeline stage 4 (Foundry PoC retry-loop) runs for HIGH/CRITICAL
    # findings. Owner may toggle off to save LLM credits during development.
    "auto_poc": True,
    # When True, pipeline stage 5 (AI-fuzzing with medusa/forge invariant) runs.
    # Most expensive stage.
    "auto_fuzzing": True,
    # When True, multi-agent triage (4 parallel Claude calls) runs.
    # When False, falls back to single-call TriageOrchestrator.
    "multi_agent_triage": True,
    # Future: 24/7 monitoring of watched addresses. Wired but not yet active.
    "continuous_monitoring": False,
    # Future: anonymise this user in any public leaderboard.
    "anonymous_in_public": False,
}


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "preferences",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text(f"'{_serialize(_DEFAULT_PREFS)}'::jsonb"),
        ),
    )
    # Backfill existing rows (server_default only applies to NEW rows on some
    # PG versions when the column is added NOT NULL).
    op.execute(
        "UPDATE users SET preferences = '" + _serialize(_DEFAULT_PREFS) + "'::jsonb"
        " WHERE preferences IS NULL OR preferences = '{}'::jsonb"
    )


def downgrade() -> None:
    op.drop_column("users", "preferences")


def _serialize(d: dict) -> str:
    import json
    return json.dumps(d).replace("'", "''")
