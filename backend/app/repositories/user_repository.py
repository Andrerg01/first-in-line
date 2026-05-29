"""Persistence layer for user accounts, profiles, credentials, and locations.

All database access for the auth domain lives here.  Services call these
functions rather than building queries directly.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.users import (
    SearchLocation,
    User,
    UserCredentialHistory,
    UserPreferredLocation,
    UserProfile,
)


# ---------------------------------------------------------------------------
# User lookup
# ---------------------------------------------------------------------------

def find_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    """Return a user by primary key, or None if not found."""
    return db.get(User, user_id)


def find_by_email(db: Session, email: str) -> User | None:
    """Return a user whose email matches (case-insensitive), or None."""
    return db.scalar(
        select(User).where(User.email == email.lower().strip())
    )


def find_by_username(db: Session, username: str) -> User | None:
    """Return a user by username (case-insensitive), or None."""
    return db.scalar(
        select(User).where(User.username == username.lower().strip())
    )


def find_by_login(db: Session, login: str) -> User | None:
    """Return a user matching the login string as email or username."""
    normalised = login.lower().strip()
    user = db.scalar(select(User).where(User.email == normalised))
    if user is None:
        user = db.scalar(select(User).where(User.username == normalised))
    return user


# ---------------------------------------------------------------------------
# User creation
# ---------------------------------------------------------------------------

def create_user(
    db: Session,
    *,
    user_id: uuid.UUID,
    email: str,
    username: str,
    password_hash: str,
) -> User:
    """Insert a new user row and return it.

    Args:
        db: Active database session.
        user_id: Pre-generated UUID (used as the password pepper).
        email: Normalised email address.
        username: Normalised username.
        password_hash: bcrypt hash (password peppered with user_id).

    Returns:
        The newly persisted ``User`` instance.
    """
    user = User(
        id=user_id,
        email=email.lower().strip(),
        username=username.lower().strip(),
        password_hash=password_hash,
    )
    db.add(user)
    db.flush()
    return user


# ---------------------------------------------------------------------------
# Credential updates + history
# ---------------------------------------------------------------------------

def record_credential_change(
    db: Session,
    *,
    user_id: uuid.UUID,
    field_changed: str,
    old_value: str | None,
    new_value: str | None,
) -> UserCredentialHistory:
    """Append an audit entry to ``user_credential_history``.

    Args:
        db: Active database session.
        user_id: Owner of the credential record.
        field_changed: One of "email", "username", or "password_hash".
        old_value: Previous value (hash for passwords, plaintext for others).
        new_value: Replacement value.

    Returns:
        The persisted ``UserCredentialHistory`` row.
    """
    entry = UserCredentialHistory(
        user_id=user_id,
        field_changed=field_changed,
        old_value=old_value,
        new_value=new_value,
    )
    db.add(entry)
    db.flush()
    return entry


def update_user_email(db: Session, user: User, new_email: str) -> User:
    """Change a user's email and record the history entry.

    Args:
        db: Active database session.
        user: The user to modify.
        new_email: Validated new email address.

    Returns:
        The updated ``User``.
    """
    record_credential_change(
        db,
        user_id=user.id,
        field_changed="email",
        old_value=user.email,
        new_value=new_email.lower().strip(),
    )
    user.email = new_email.lower().strip()
    user.updated_at = datetime.now(timezone.utc)
    db.flush()
    return user


def update_user_username(db: Session, user: User, new_username: str) -> User:
    """Change a user's username and record the history entry.

    Args:
        db: Active database session.
        user: The user to modify.
        new_username: Validated new username.

    Returns:
        The updated ``User``.
    """
    record_credential_change(
        db,
        user_id=user.id,
        field_changed="username",
        old_value=user.username,
        new_value=new_username.lower().strip(),
    )
    user.username = new_username.lower().strip()
    user.updated_at = datetime.now(timezone.utc)
    db.flush()
    return user


def update_user_password(db: Session, user: User, new_hash: str) -> User:
    """Replace a user's password hash and record the history entry.

    The old hash (not the plaintext) is stored in history for audit purposes.

    Args:
        db: Active database session.
        user: The user to modify.
        new_hash: New bcrypt hash string.

    Returns:
        The updated ``User``.
    """
    record_credential_change(
        db,
        user_id=user.id,
        field_changed="password_hash",
        old_value=user.password_hash,
        new_value=new_hash,
    )
    user.password_hash = new_hash
    user.updated_at = datetime.now(timezone.utc)
    db.flush()
    return user


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

def get_profile(db: Session, user_id: uuid.UUID) -> UserProfile | None:
    """Return the profile for a user, or None if not yet created."""
    return db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))


def upsert_profile(
    db: Session,
    *,
    user_id: uuid.UUID,
    first_name: str | None,
    middle_initial: str | None,
    last_name: str | None,
    phone_number: str | None,
) -> UserProfile:
    """Create or update a user's profile.

    Args:
        db: Active database session.
        user_id: Owner of the profile.
        first_name: Optional first name.
        middle_initial: Optional single middle initial.
        last_name: Optional last name.
        phone_number: Optional phone number string.

    Returns:
        The created or updated ``UserProfile``.
    """
    profile = get_profile(db, user_id)
    if profile is None:
        profile = UserProfile(user_id=user_id)
        db.add(profile)

    profile.first_name = first_name
    profile.middle_initial = middle_initial
    profile.last_name = last_name
    profile.phone_number = phone_number
    profile.updated_at = datetime.now(timezone.utc)
    db.flush()
    return profile


# ---------------------------------------------------------------------------
# Preferred locations
# ---------------------------------------------------------------------------

def get_preferred_locations(
    db: Session, user_id: uuid.UUID
) -> list[UserPreferredLocation]:
    """Return all preferred locations for a user."""
    return list(
        db.scalars(
            select(UserPreferredLocation)
            .where(UserPreferredLocation.user_id == user_id)
            .order_by(UserPreferredLocation.created_at)
        )
    )


def find_preferred_location(
    db: Session, user_id: uuid.UUID, city: str, state: str
) -> UserPreferredLocation | None:
    """Return an existing preferred location row, or None."""
    return db.scalar(
        select(UserPreferredLocation).where(
            UserPreferredLocation.user_id == user_id,
            UserPreferredLocation.city == city,
            UserPreferredLocation.state == state.upper(),
        )
    )


def add_preferred_location(
    db: Session, *, user_id: uuid.UUID, city: str, state: str
) -> UserPreferredLocation:
    """Add a preferred location for a user.

    Args:
        db: Active database session.
        user_id: Owner of the preference.
        city: City name.
        state: Two-letter US state code (uppercased).

    Returns:
        The new ``UserPreferredLocation`` row.
    """
    loc = UserPreferredLocation(user_id=user_id, city=city, state=state.upper())
    db.add(loc)
    db.flush()
    return loc


def remove_preferred_location(
    db: Session, *, user_id: uuid.UUID, location_id: uuid.UUID
) -> bool:
    """Delete a preferred location owned by the given user.

    Args:
        db: Active database session.
        user_id: Requesting user (must own the record).
        location_id: UUID of the location to remove.

    Returns:
        True if the row was found and deleted, False otherwise.
    """
    loc = db.scalar(
        select(UserPreferredLocation).where(
            UserPreferredLocation.id == location_id,
            UserPreferredLocation.user_id == user_id,
        )
    )
    if loc is None:
        return False
    db.delete(loc)
    db.flush()
    return True


# ---------------------------------------------------------------------------
# Search locations
# ---------------------------------------------------------------------------

def find_search_location(db: Session, city: str, state: str) -> SearchLocation | None:
    """Return a search location by city + state, or None."""
    return db.scalar(
        select(SearchLocation).where(
            SearchLocation.city == city,
            SearchLocation.state == state.upper(),
        )
    )


def upsert_search_location(db: Session, *, city: str, state: str) -> SearchLocation:
    """Insert or increment the user_count for a search location.

    Args:
        db: Active database session.
        city: City name.
        state: Two-letter US state code.

    Returns:
        The ``SearchLocation`` row (new or existing).
    """
    loc = find_search_location(db, city, state)
    if loc is None:
        loc = SearchLocation(city=city, state=state.upper(), is_default=False, user_count=1)
        db.add(loc)
    else:
        loc.user_count += 1
    db.flush()
    return loc
