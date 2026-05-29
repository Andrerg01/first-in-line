"""Reorganise all tables into named schemas.

Revision ID: 0007_schemas
Revises: 0006_users
Create Date: 2026-05-28

Changes
-------
Creates four named PostgreSQL schemas and moves every existing table out of
``public`` into the appropriate schema:

* ``events``    — events, event_claims, event_sources
* ``ingestion`` — source_documents, locations, search_runs, search_results,
                  search_locations
* ``users``     — users, user_profiles, user_credential_history,
                  user_preferred_locations
* ``logs``      — llm_calls, pipeline_tool_calls, processing_decisions

PostgreSQL preserves FK constraints across ``ALTER TABLE … SET SCHEMA``
because constraints are stored by OID, not by schema-qualified name.
The ``alembic_version`` table is left in ``public``.
"""
from __future__ import annotations

from alembic import op

revision: str = "0007_schemas"
down_revision: str | None = "0006_users"
branch_labels: str | None = None
depends_on: str | None = None

# ---------------------------------------------------------------------------
# Schema → table mapping (upgrade order matters for FK safety, but
# SET SCHEMA does not drop/recreate FKs so order is flexible).
# ---------------------------------------------------------------------------
_SCHEMA_TABLES: dict[str, list[str]] = {
    "events": ["events", "event_claims", "event_sources"],
    "ingestion": [
        "source_documents",
        "locations",
        "search_runs",
        "search_results",
        "search_locations",
    ],
    "users": [
        "users",
        "user_profiles",
        "user_credential_history",
        "user_preferred_locations",
    ],
    "logs": ["llm_calls", "pipeline_tool_calls", "processing_decisions"],
}


def upgrade() -> None:
    """Create schemas and move tables out of public."""
    for schema in _SCHEMA_TABLES:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    for schema, tables in _SCHEMA_TABLES.items():
        for table in tables:
            op.execute(f"ALTER TABLE public.{table} SET SCHEMA {schema}")


def downgrade() -> None:
    """Move all tables back to public and drop the named schemas."""
    for schema, tables in _SCHEMA_TABLES.items():
        for table in tables:
            op.execute(f"ALTER TABLE {schema}.{table} SET SCHEMA public")

    for schema in _SCHEMA_TABLES:
        op.execute(f"DROP SCHEMA IF EXISTS {schema}")
