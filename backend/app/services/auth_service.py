"""Business logic for user registration, login, and account management.

This service is the single point of truth for auth rules.  All password
verification, token generation, and credential-change logic lives here.
Routers call this service; the service calls the repository.
"""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.users import User, UserPreferredLocation, UserProfile
from app.repositories import user_repository as repo
from app.schemas.users import (
    EmailUpdate,
    PasswordUpdate,
    PreferredLocationCreate,
    UserLogin,
    UserProfileUpdate,
    UserRegister,
    UsernameUpdate,
)
from app.utils.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(db: Session, data: UserRegister) -> tuple[User, str]:
    """Create a new user account and return the user + JWT token.

    Args:
        db: Active database session.
        data: Validated registration payload.

    Returns:
        Tuple of (User, access_token_string).

    Raises:
        HTTPException 409: If the email or username is already taken.
    """
    if repo.find_by_email(db, data.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )
    if repo.find_by_username(db, data.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username is already taken.",
        )

    user_id = uuid.uuid4()
    password_hash = hash_password(data.password, user_id)
    user = repo.create_user(
        db,
        user_id=user_id,
        email=data.email,
        username=data.username,
        password_hash=password_hash,
    )
    db.commit()
    db.refresh(user)
    return user, create_access_token(user.id)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def login(db: Session, data: UserLogin) -> tuple[User, str]:
    """Authenticate a user by email-or-username + password.

    Args:
        db: Active database session.
        data: Validated login payload.

    Returns:
        Tuple of (User, access_token_string).

    Raises:
        HTTPException 401: If credentials are invalid or account inactive.
    """
    user = repo.find_by_login(db, data.login)
    if user is None or not verify_password(data.password, user.id, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )
    return user, create_access_token(user.id)


# ---------------------------------------------------------------------------
# FastAPI dependency: current authenticated user
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency that resolves the Bearer token to a User.

    Raises:
        HTTPException 401: If no token, invalid token, or unknown user.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = repo.find_by_id(db, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated.",
        )
    return user


# ---------------------------------------------------------------------------
# Credential updates
# ---------------------------------------------------------------------------

def update_email(db: Session, user: User, data: EmailUpdate) -> User:
    """Change the user's email after verifying their current password.

    Args:
        db: Active database session.
        user: Authenticated user requesting the change.
        data: Validated email-update payload.

    Returns:
        Updated ``User``.

    Raises:
        HTTPException 401: Wrong current password.
        HTTPException 409: New email already in use.
    """
    if not verify_password(data.current_password, user.id, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect.",
        )
    if repo.find_by_email(db, data.new_email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That email address is already in use.",
        )
    user = repo.update_user_email(db, user, data.new_email)
    db.commit()
    db.refresh(user)
    return user


def update_username(db: Session, user: User, data: UsernameUpdate) -> User:
    """Change the user's username.

    Args:
        db: Active database session.
        user: Authenticated user requesting the change.
        data: Validated username-update payload.

    Returns:
        Updated ``User``.

    Raises:
        HTTPException 409: New username already in use.
    """
    if repo.find_by_username(db, data.new_username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username is already taken.",
        )
    user = repo.update_user_username(db, user, data.new_username)
    db.commit()
    db.refresh(user)
    return user


def update_password(db: Session, user: User, data: PasswordUpdate) -> User:
    """Change the user's password after verifying the current one.

    Args:
        db: Active database session.
        user: Authenticated user requesting the change.
        data: Validated password-update payload.

    Returns:
        Updated ``User``.

    Raises:
        HTTPException 401: Wrong current password.
    """
    if not verify_password(data.current_password, user.id, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect.",
        )
    new_hash = hash_password(data.new_password, user.id)
    user = repo.update_user_password(db, user, new_hash)
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

def get_or_create_profile(db: Session, user: User) -> UserProfile:
    """Return the user's profile, creating an empty one if absent.

    Args:
        db: Active database session.
        user: Owner of the profile.

    Returns:
        The ``UserProfile`` (existing or newly created).
    """
    profile = repo.get_profile(db, user.id)
    if profile is None:
        profile = repo.upsert_profile(
            db,
            user_id=user.id,
            first_name=None,
            middle_initial=None,
            last_name=None,
            phone_number=None,
        )
        db.commit()
        db.refresh(profile)
    return profile


def update_profile(db: Session, user: User, data: UserProfileUpdate) -> UserProfile:
    """Create or overwrite a user's profile.

    Args:
        db: Active database session.
        user: Authenticated owner.
        data: Validated profile payload.

    Returns:
        The updated ``UserProfile``.
    """
    profile = repo.upsert_profile(
        db,
        user_id=user.id,
        first_name=data.first_name,
        middle_initial=data.middle_initial,
        last_name=data.last_name,
        phone_number=data.phone_number,
    )
    db.commit()
    db.refresh(profile)
    return profile


# ---------------------------------------------------------------------------
# Preferred locations
# ---------------------------------------------------------------------------

def add_preferred_location(
    db: Session, user: User, data: PreferredLocationCreate
) -> UserPreferredLocation:
    """Add a preferred location for the user and upsert into search_locations.

    If the user already has this city/state, the existing row is returned
    without creating a duplicate.

    Args:
        db: Active database session.
        user: Authenticated owner.
        data: Validated location payload.

    Returns:
        The ``UserPreferredLocation`` row.
    """
    city = data.city.strip().title()
    state = data.state.upper()

    existing = repo.find_preferred_location(db, user.id, city, state)
    if existing:
        return existing

    loc = repo.add_preferred_location(db, user_id=user.id, city=city, state=state)
    # Also upsert into the global search_locations table
    repo.upsert_search_location(db, city=city, state=state)
    db.commit()
    db.refresh(loc)
    return loc


def remove_preferred_location(
    db: Session, user: User, location_id: uuid.UUID
) -> None:
    """Remove a preferred location owned by the user.

    Args:
        db: Active database session.
        user: Authenticated owner.
        location_id: UUID of the location row to delete.

    Raises:
        HTTPException 404: Location not found or not owned by user.
    """
    found = repo.remove_preferred_location(db, user_id=user.id, location_id=location_id)
    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found.",
        )
    db.commit()
