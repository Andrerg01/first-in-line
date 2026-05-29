"""Auth router — registration, login, and account-management endpoints.

All routes are prefixed with /api/auth.
Protected routes require a valid Bearer token resolved via
``auth_service.get_current_user``.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.users import User
from app.schemas.users import (
    EmailUpdate,
    PasswordUpdate,
    PreferredLocationCreate,
    PreferredLocationPublic,
    TokenResponse,
    UserLogin,
    UserProfilePublic,
    UserProfileUpdate,
    UserPublic,
    UserRegister,
    UsernameUpdate,
)
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Public: register + login
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(data: UserRegister, db: Session = Depends(get_db)) -> TokenResponse:
    """Create a new account and return a JWT token."""
    user, token = auth_service.register(db, data)
    return TokenResponse(access_token=token, user=UserPublic.model_validate(user))


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and receive a JWT token",
)
def login(data: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate with email-or-username + password."""
    user, token = auth_service.login(db, data)
    return TokenResponse(access_token=token, user=UserPublic.model_validate(user))


# ---------------------------------------------------------------------------
# Protected: current user
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=UserPublic,
    summary="Get the authenticated user's account info",
)
def get_me(current_user: User = Depends(auth_service.get_current_user)) -> UserPublic:
    """Return account info for the authenticated user."""
    return UserPublic.model_validate(current_user)


# ---------------------------------------------------------------------------
# Protected: credential updates
# ---------------------------------------------------------------------------

@router.put(
    "/me/email",
    response_model=UserPublic,
    summary="Change email address (requires current password)",
)
def change_email(
    data: EmailUpdate,
    current_user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
) -> UserPublic:
    """Update the authenticated user's email address."""
    user = auth_service.update_email(db, current_user, data)
    return UserPublic.model_validate(user)


@router.put(
    "/me/username",
    response_model=UserPublic,
    summary="Change username",
)
def change_username(
    data: UsernameUpdate,
    current_user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
) -> UserPublic:
    """Update the authenticated user's username."""
    user = auth_service.update_username(db, current_user, data)
    return UserPublic.model_validate(user)


@router.put(
    "/me/password",
    response_model=UserPublic,
    summary="Change password (requires current password)",
)
def change_password(
    data: PasswordUpdate,
    current_user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
) -> UserPublic:
    """Update the authenticated user's password."""
    user = auth_service.update_password(db, current_user, data)
    return UserPublic.model_validate(user)


# ---------------------------------------------------------------------------
# Protected: profile
# ---------------------------------------------------------------------------

@router.get(
    "/me/profile",
    response_model=UserProfilePublic,
    summary="Get profile (name, phone)",
)
def get_profile(
    current_user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
) -> UserProfilePublic:
    """Return the authenticated user's profile, creating an empty one if absent."""
    profile = auth_service.get_or_create_profile(db, current_user)
    return UserProfilePublic.model_validate(profile)


@router.put(
    "/me/profile",
    response_model=UserProfilePublic,
    summary="Create or update profile",
)
def update_profile(
    data: UserProfileUpdate,
    current_user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
) -> UserProfilePublic:
    """Create or overwrite the authenticated user's profile."""
    profile = auth_service.update_profile(db, current_user, data)
    return UserProfilePublic.model_validate(profile)


# ---------------------------------------------------------------------------
# Protected: preferred locations
# ---------------------------------------------------------------------------

@router.get(
    "/me/locations",
    response_model=list[PreferredLocationPublic],
    summary="List preferred locations",
)
def list_locations(
    current_user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
) -> list[PreferredLocationPublic]:
    """Return all preferred city/state locations for the authenticated user."""
    from app.repositories import user_repository as repo
    locs = repo.get_preferred_locations(db, current_user.id)
    return [PreferredLocationPublic.model_validate(l) for l in locs]


@router.post(
    "/me/locations",
    response_model=PreferredLocationPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Add a preferred location",
)
def add_location(
    data: PreferredLocationCreate,
    current_user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
) -> PreferredLocationPublic:
    """Add a city/state to the user's preferred locations (idempotent)."""
    loc = auth_service.add_preferred_location(db, current_user, data)
    return PreferredLocationPublic.model_validate(loc)


@router.delete(
    "/me/locations/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Remove a preferred location",
)
def remove_location(
    location_id: uuid.UUID,
    current_user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Remove a preferred location owned by the authenticated user."""
    auth_service.remove_preferred_location(db, current_user, location_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
