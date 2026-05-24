"""Add telemetry: pipeline_tool_calls table and run stats columns.

Revision ID: 0002_telemetry
Revises: 0001_initial_schema
Create Date: 2026-05-24

Changes
-------
1. Add aggregate stats columns to ``search_runs`` so the final state of a run
   can be queried without joining to child tables.
2. Create ``pipeline_tool_calls`` to record every MCP and backend tool call
   made during a pipeline run — enables per-run diagnostics, rate-limit
   pattern analysis, and latency trending.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "0002_telemetry"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Apply telemetry schema additions."""

    # ------------------------------------------------------------------
    # 1. Aggregate stats on search_runs
    # ------------------------------------------------------------------
    op.add_column(
        "search_runs",
        sa.Column("queries_executed", sa.Integer(), nullable=True),
    )
    op.add_column(
        "search_runs",
        sa.Column("search_results_found", sa.Integer(), nullable=True),
    )
    op.add_column(
        "search_runs",
        sa.Column("urls_attempted", sa.Integer(), nullable=True),
    )
    op.add_column(
        "search_runs",
        sa.Column("source_docs_created", sa.Integer(), nullable=True),
    )
    op.add_column(
        "search_runs",
        sa.Column("source_docs_skipped", sa.Integer(), nullable=True),
    )
    op.add_column(
        "search_runs",
        sa.Column("fetch_errors", sa.Integer(), nullable=True),
    )
    op.add_column(
        "search_runs",
        sa.Column("elapsed_seconds", sa.Numeric(10, 3), nullable=True),
    )

    # ------------------------------------------------------------------
    # 2. pipeline_tool_calls
    # ------------------------------------------------------------------
    op.create_table(
        "pipeline_tool_calls",
        sa.Column("id", sa.UUID(), nullable=False, default=uuid.uuid4),
        sa.Column("search_run_id", sa.UUID(), nullable=False),
        # The logical tool being called, e.g. 'web.search', 'web.fetch_page',
        # 'web.normalize_text', 'backend.store_source_doc'.
        sa.Column("tool_name", sa.String(60), nullable=False),
        # Truncated key input — query text or URL (≤ 200 chars).
        sa.Column("input_summary", sa.Text(), nullable=True),
        # Outcome code: success | error | timeout | rate_limit | duplicate | skipped
        sa.Column("outcome", sa.String(20), nullable=False),
        # Wall-clock duration of the call in milliseconds.
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        # HTTP status returned by MCP server or backend API, if applicable.
        sa.Column("http_status", sa.Integer(), nullable=True),
        # Error detail when outcome != 'success'.
        sa.Column("error_message", sa.Text(), nullable=True),
        # Which retry attempt (1 = first try).
        sa.Column(
            "attempt_number",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["search_run_id"], ["search_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pipeline_tool_calls_search_run_id",
        "pipeline_tool_calls",
        ["search_run_id"],
    )
    op.create_index(
        "ix_pipeline_tool_calls_tool_name",
        "pipeline_tool_calls",
        ["tool_name"],
    )
    op.create_index(
        "ix_pipeline_tool_calls_outcome",
        "pipeline_tool_calls",
        ["outcome"],
    )


def downgrade() -> None:
    """Revert telemetry schema additions."""
    op.drop_index("ix_pipeline_tool_calls_outcome", "pipeline_tool_calls")
    op.drop_index("ix_pipeline_tool_calls_tool_name", "pipeline_tool_calls")
    op.drop_index(
        "ix_pipeline_tool_calls_search_run_id", "pipeline_tool_calls"
    )
    op.drop_table("pipeline_tool_calls")

    for col in (
        "elapsed_seconds",
        "fetch_errors",
        "source_docs_skipped",
        "source_docs_created",
        "urls_attempted",
        "search_results_found",
        "queries_executed",
    ):
        op.drop_column("search_runs", col)
