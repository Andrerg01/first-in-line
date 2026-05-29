"""Create user authentication and location tables.

Revision ID: 0006_users
Revises: 0005_date_confidence
Create Date: 2026-05-28

Changes
-------
1. ``users``                   — core credentials, tier, role.
2. ``user_profiles``           — optional display name and phone.
3. ``user_credential_history`` — append-only audit log for email/username/password changes.
4. ``user_preferred_locations``— cities/states the user follows.
5. ``search_locations``        — normalised location set for the worker; seeded with
                                  Greenville, SC as the default.
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "0006_users"
down_revision: str | None = "0005_date_confidence"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create all user-related tables and seed the default search location."""

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "tier", sa.String(30), nullable=False, server_default=sa.text("'basic'")
        ),
        sa.Column(
            "role", sa.String(30), nullable=False, server_default=sa.text("'user'")
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
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
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])

    # ------------------------------------------------------------------
    # user_profiles
    # ------------------------------------------------------------------
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("middle_initial", sa.String(5), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("phone_number", sa.String(30), nullable=True),
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
        sa.UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    # ------------------------------------------------------------------
    # user_credential_history
    # ------------------------------------------------------------------
    op.create_table(
        "user_credential_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("field_changed", sa.String(30), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ucredh_user_id", "user_credential_history", ["user_id"])
    op.create_index("ix_ucredh_changed_at", "user_credential_history", ["changed_at"])

    # ------------------------------------------------------------------
    # user_preferred_locations
    # ------------------------------------------------------------------
    op.create_table(
        "user_preferred_locations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("city", sa.String(120), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_upref_user_id", "user_preferred_locations", ["user_id"]
    )

    # ------------------------------------------------------------------
    # search_locations
    # ------------------------------------------------------------------
    op.create_table(
        "search_locations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("city", sa.String(120), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "user_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("city", "state", name="uq_search_locations_city_state"),
    )
    op.create_index(
        "ix_search_loc_city_state", "search_locations", ["city", "state"], unique=True
    )

    # Seed the default search location
    seed_id = str(uuid.uuid4())
    op.execute(
        sa.text(
            f"INSERT INTO search_locations (id, city, state, is_default, user_count) "
            f"VALUES ('{seed_id}'::uuid, 'Greenville', 'SC', true, 0)"
        )
    )


def downgrade() -> None:
    """Drop all user-related tables (search_locations last due to no FK deps)."""
    op.drop_table("user_preferred_locations")
    op.drop_table("user_credential_history")
    op.drop_table("user_profiles")
    op.drop_table("users")
    op.drop_table("search_locations")
