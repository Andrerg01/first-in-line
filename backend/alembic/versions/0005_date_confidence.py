"""Add date confidence and range columns to events table.

Revision ID: 0005_date_confidence
Revises: 0004_dedup_columns
Create Date: 2026-05-24

Changes
-------
1. Add ``date_confidence`` VARCHAR(20) nullable — values: exact | month | season | year | unknown.
2. Add ``date_range_start`` DATE nullable — lower bound of the event date range.
3. Add ``date_range_end`` DATE nullable — upper bound of the event date range.

``event_date`` is not touched; it remains the best-guess single date for backward
compatibility.  The new columns allow the ingestion layer to express date uncertainty
(e.g. "coming summer 2026") as a range with a named confidence level.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0005_date_confidence"
down_revision: str | None = "0004_dedup_columns"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Add date_confidence, date_range_start, and date_range_end to events."""
    op.add_column(
        "events",
        sa.Column("date_confidence", sa.String(20), nullable=True),
    )
    op.add_column(
        "events",
        sa.Column("date_range_start", sa.Date(), nullable=True),
    )
    op.add_column(
        "events",
        sa.Column("date_range_end", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    """Remove date confidence and range columns from events."""
    op.drop_column("events", "date_range_end")
    op.drop_column("events", "date_range_start")
    op.drop_column("events", "date_confidence")
