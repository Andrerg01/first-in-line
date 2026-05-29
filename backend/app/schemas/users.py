"""Pydantic schemas for user authentication, profile, and location endpoints."""
from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,50}$")


def _validate_username(value: str) -> str:
    if not _USERNAME_RE.match(value):
        raise ValueError(
            "Username must be 3–50 characters and contain only letters, digits, or underscores."
        )
    return value


def _validate_password_strength(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters.")
    return value


# ---------------------------------------------------------------------------
# Registration / login
# ---------------------------------------------------------------------------

class UserRegister(BaseModel):
    """Payload for POST /api/auth/register."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    password_confirmation: str

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        return _validate_username(v)

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return _validate_password_strength(v)

    @field_validator("password_confirmation")
    @classmethod
    def passwords_match(cls, v: str, info: object) -> str:  # type: ignore[override]
        data = getattr(info, "data", {})
        if "password" in data and v != data["password"]:
            raise ValueError("Passwords do not match.")
        return v


class UserLogin(BaseModel):
    """Payload for POST /api/auth/login.  Accepts email or username."""

    login: str = Field(..., description="Email address or username")
    password: str


# ---------------------------------------------------------------------------
# Public user representation
# ---------------------------------------------------------------------------

class UserPublic(BaseModel):
    """Safe public view of a user account (no password hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str
    tier: str
    role: str
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    """Response returned on successful login or registration."""

    access_token: str
    token_type: str = "bearer"
    user: UserPublic


# ---------------------------------------------------------------------------
# Credential updates
# ---------------------------------------------------------------------------

class EmailUpdate(BaseModel):
    """Payload for PUT /api/auth/me/email."""

    current_password: str
    new_email: EmailStr


class UsernameUpdate(BaseModel):
    """Payload for PUT /api/auth/me/username."""

    new_username: str = Field(..., min_length=3, max_length=50)

    @field_validator("new_username")
    @classmethod
    def check_username(cls, v: str) -> str:
        return _validate_username(v)


class PasswordUpdate(BaseModel):
    """Payload for PUT /api/auth/me/password."""

    current_password: str
    new_password: str = Field(..., min_length=8)
    new_password_confirmation: str

    @field_validator("new_password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return _validate_password_strength(v)

    @field_validator("new_password_confirmation")
    @classmethod
    def passwords_match(cls, v: str, info: object) -> str:  # type: ignore[override]
        data = getattr(info, "data", {})
        if "new_password" in data and v != data["new_password"]:
            raise ValueError("Passwords do not match.")
        return v


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

class UserProfileUpdate(BaseModel):
    """Payload for PUT /api/auth/me/profile.  All fields optional."""

    first_name: str | None = Field(None, max_length=100)
    middle_initial: str | None = Field(None, max_length=5)
    last_name: str | None = Field(None, max_length=100)
    phone_number: str | None = Field(None, max_length=30)


class UserProfilePublic(BaseModel):
    """Response for profile endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    first_name: str | None
    middle_initial: str | None
    last_name: str | None
    phone_number: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Preferred locations
# ---------------------------------------------------------------------------

class PreferredLocationCreate(BaseModel):
    """Payload for POST /api/auth/me/locations."""

    city: str = Field(..., min_length=1, max_length=120)
    state: str = Field(..., min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")


class PreferredLocationPublic(BaseModel):
    """Response for preferred location list."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    city: str
    state: str
    created_at: datetime
