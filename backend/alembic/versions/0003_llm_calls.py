"""Add llm_calls table and llm_call_id FK on processing_decisions.

Revision ID: 0003_llm_calls
Revises: 0002_telemetry
Create Date: 2026-05-24

Changes
-------
1. Create ``llm_calls`` table — records every OpenAI API call made during
   the extraction pipeline with token counts, estimated cost, and latency.
2. Add nullable ``llm_call_id`` FK on ``processing_decisions`` so each
   decision can be linked back to the LLM call that produced it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0003_llm_calls"
down_revision: str | None = "0002_telemetry"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Apply llm_calls schema additions."""

    op.create_table(
        "llm_calls",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("call_type", sa.String(60), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="success",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column(
        "processing_decisions",
        sa.Column(
            "llm_call_id",
            sa.UUID(),
            sa.ForeignKey("llm_calls.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Revert llm_calls schema additions."""
    op.drop_column("processing_decisions", "llm_call_id")
    op.drop_table("llm_calls")
