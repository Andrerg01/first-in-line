"""Initial schema: create all Phase 1 tables.

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-05-23

"""

from __future__ import annotations

import uuid
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create all Phase 1 tables."""

    op.create_table(
        "locations",
        sa.Column("id", sa.UUID(), nullable=False, default=uuid.uuid4),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("city", sa.String(120), nullable=False),
        sa.Column("state", sa.String(60), nullable=False),
        sa.Column("country", sa.String(60), nullable=False, server_default="US"),
        sa.Column("lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("lon", sa.Numeric(9, 6), nullable=True),
        sa.Column("radius_miles", sa.Numeric(6, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "search_runs",
        sa.Column("id", sa.UUID(), nullable=False, default=uuid.uuid4),
        sa.Column("location_id", sa.UUID(), nullable=True),
        sa.Column("run_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("query_set_version", sa.String(40), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["location_id"], ["locations.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "search_results",
        sa.Column("id", sa.UUID(), nullable=False, default=uuid.uuid4),
        sa.Column("search_run_id", sa.UUID(), nullable=False),
        sa.Column("query", sa.Text(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("search_provider", sa.String(60), nullable=True),
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

    op.create_table(
        "source_documents",
        sa.Column("id", sa.UUID(), nullable=False, default=uuid.uuid4),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("visible_text", sa.Text(), nullable=True),
        sa.Column("visible_text_hash", sa.String(64), nullable=True),
        sa.Column("fetch_status", sa.String(20), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(120), nullable=True),
        sa.Column("fetch_method", sa.String(40), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "visible_text_hash", name="uq_source_documents_text_hash"
        ),
    )
    op.create_index(
        "ix_source_documents_canonical_url", "source_documents", ["canonical_url"]
    )
    op.create_index("ix_source_documents_domain", "source_documents", ["domain"])
    op.create_index(
        "ix_source_documents_fetched_at", "source_documents", ["fetched_at"]
    )

    op.create_table(
        "events",
        sa.Column("id", sa.UUID(), nullable=False, default=uuid.uuid4),
        sa.Column("business_name", sa.Text(), nullable=True),
        sa.Column("event_name", sa.Text(), nullable=True),
        sa.Column("event_type", sa.String(40), nullable=False, server_default="unknown"),
        sa.Column("category", sa.String(60), nullable=True),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(120), nullable=True),
        sa.Column("state", sa.String(60), nullable=True),
        sa.Column("country", sa.String(60), nullable=True, server_default="US"),
        sa.Column("lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("lon", sa.Numeric(9, 6), nullable=True),
        sa.Column("promotion_text", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="candidate"),
        sa.Column("confidence_score", sa.Numeric(4, 3), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_event_date", "events", ["event_date"])
    op.create_index("ix_events_city_state", "events", ["city", "state"])
    op.create_index("ix_events_status", "events", ["status"])
    op.create_index("ix_events_business_name", "events", ["business_name"])

    op.create_table(
        "event_sources",
        sa.Column("id", sa.UUID(), nullable=False, default=uuid.uuid4),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("source_document_id", sa.UUID(), nullable=False),
        sa.Column(
            "relationship_type",
            sa.String(40),
            nullable=False,
            server_default="primary_source",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["source_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "event_claims",
        sa.Column("id", sa.UUID(), nullable=False, default=uuid.uuid4),
        sa.Column("event_id", sa.UUID(), nullable=True),
        sa.Column("source_document_id", sa.UUID(), nullable=False),
        sa.Column("claim_type", sa.String(40), nullable=False),
        sa.Column("claim_value", sa.Text(), nullable=True),
        sa.Column("claim_text", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(4, 3), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["event_id"], ["events.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["source_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "processing_decisions",
        sa.Column("id", sa.UUID(), nullable=False, default=uuid.uuid4),
        sa.Column("source_document_id", sa.UUID(), nullable=True),
        sa.Column("event_id", sa.UUID(), nullable=True),
        sa.Column("decision_type", sa.String(60), nullable=False),
        sa.Column("decision_value", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["source_documents.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["event_id"], ["events.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Drop all Phase 1 tables in reverse dependency order."""
    op.drop_table("processing_decisions")
    op.drop_table("event_claims")
    op.drop_table("event_sources")
    op.drop_index("ix_events_business_name", table_name="events")
    op.drop_index("ix_events_status", table_name="events")
    op.drop_index("ix_events_city_state", table_name="events")
    op.drop_index("ix_events_event_date", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_source_documents_fetched_at", table_name="source_documents")
    op.drop_index("ix_source_documents_domain", table_name="source_documents")
    op.drop_index("ix_source_documents_canonical_url", table_name="source_documents")
    op.drop_table("source_documents")
    op.drop_table("search_results")
    op.drop_table("search_runs")
    op.drop_table("locations")
