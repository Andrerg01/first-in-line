"""Add deduplication columns to events table.

Revision ID: 0004_dedup_columns
Revises: 0003_llm_calls
Create Date: 2026-05-24

Changes
-------
1. Add ``possible_duplicate`` boolean flag on ``events`` — set to True when
   a newly ingested candidate closely resembles an existing record.
2. Add nullable ``duplicate_of_id`` FK on ``events`` pointing at the
   suspected canonical event record.
3. Add ``normalized_business_name`` text column — stores the normalized
   form of the business name used for similarity comparisons (populated
   by the dedup service at save time).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0004_dedup_columns"
down_revision: str | None = "0003_llm_calls"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Apply dedup column additions to events."""

    op.add_column(
        "events",
        sa.Column(
            "possible_duplicate",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "events",
        sa.Column(
            "duplicate_of_id",
            sa.UUID(),
            nullable=True,
        ),
    )
    op.add_column(
        "events",
        sa.Column(
            "normalized_business_name",
            sa.Text(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_events_duplicate_of_id",
        "events",
        "events",
        ["duplicate_of_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_events_possible_duplicate",
        "events",
        ["possible_duplicate"],
    )
    op.create_index(
        "ix_events_normalized_business_name",
        "events",
        ["normalized_business_name"],
    )


def downgrade() -> None:
    """Remove dedup columns from events."""
    op.drop_index("ix_events_normalized_business_name", table_name="events")
    op.drop_index("ix_events_possible_duplicate", table_name="events")
    op.drop_constraint("fk_events_duplicate_of_id", "events", type_="foreignkey")
    op.drop_column("events", "normalized_business_name")
    op.drop_column("events", "duplicate_of_id")
    op.drop_column("events", "possible_duplicate")
