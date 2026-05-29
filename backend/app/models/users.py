"""User authentication and account ORM models.

Four tables are defined here:

* ``users``                  — core credentials (email, username, password hash)
* ``user_profiles``          — optional display information (name, phone)
* ``user_credential_history``— append-only audit log of credential changes
* ``user_preferred_locations``— cities/states the user wants to follow
* ``search_locations``       — normalised set of locations the worker should search
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------

class User(Base):
    """Core user account: credentials, tier, and role."""

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email", "email", unique=True),
        Index("ix_users_username", "username", unique=True),
        Index("ix_users_role", "role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    # Subscription tier — "basic" by default; future tiers can be added here
    tier: Mapped[str] = mapped_column(
        String(30), nullable=False, default="basic", server_default="basic"
    )
    # Access role — "user" | "admin" | "developer"
    role: Mapped[str] = mapped_column(
        String(30), nullable=False, default="user", server_default="user"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    # Relationships
    profile: Mapped[UserProfile | None] = relationship(
        "UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    credential_history: Mapped[list[UserCredentialHistory]] = relationship(
        "UserCredentialHistory", back_populates="user", cascade="all, delete-orphan"
    )
    preferred_locations: Mapped[list[UserPreferredLocation]] = relationship(
        "UserPreferredLocation", back_populates="user", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# user_profiles
# ---------------------------------------------------------------------------

class UserProfile(Base):
    """Optional display-name and contact information for a user."""

    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    middle_initial: Mapped[str | None] = mapped_column(String(5), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    user: Mapped[User] = relationship("User", back_populates="profile")


# ---------------------------------------------------------------------------
# user_credential_history
# ---------------------------------------------------------------------------

class UserCredentialHistory(Base):
    """Append-only audit log for credential changes (email, username, password).

    Old values are stored for audit purposes; passwords are stored as hashes
    only — the plaintext is never persisted.
    """

    __tablename__ = "user_credential_history"
    __table_args__ = (
        Index("ix_ucredh_user_id", "user_id"),
        Index("ix_ucredh_changed_at", "changed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # "email" | "username" | "password_hash"
    field_changed: Mapped[str] = mapped_column(String(30), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    user: Mapped[User] = relationship("User", back_populates="credential_history")


# ---------------------------------------------------------------------------
# user_preferred_locations
# ---------------------------------------------------------------------------

class UserPreferredLocation(Base):
    """City/state pairs that a user has opted into following."""

    __tablename__ = "user_preferred_locations"
    __table_args__ = (
        Index("ix_upref_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    user: Mapped[User] = relationship("User", back_populates="preferred_locations")


# ---------------------------------------------------------------------------
# search_locations
# ---------------------------------------------------------------------------

class SearchLocation(Base):
    """Normalised set of city/state locations the worker should search.

    Seeded with Greenville, SC as the default.  New rows are inserted
    (or their ``user_count`` incremented) when users add preferred locations.
    """

    __tablename__ = "search_locations"
    __table_args__ = (
        Index("ix_search_loc_city_state", "city", "state", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # How many users have this as a preferred location
    user_count: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
