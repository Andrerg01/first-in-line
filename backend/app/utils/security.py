"""Password hashing and JWT utilities.

Password strategy: bcrypt with the user's UUID as a pepper mixed into the
plaintext before hashing.  The UUID is stable across credential changes, so
verification always succeeds with the same user_id + raw password.

JWT strategy: HS256-signed tokens containing ``sub`` (user_id string) and
``exp`` (UTC expiry).  The secret is read from ``settings.jwt_secret``; set
``JWT_SECRET`` in the environment for production deployments.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings


def hash_password(password: str, user_id: uuid.UUID) -> str:
    """Hash a password with bcrypt, using the user's UUID as a pepper.

    Args:
        password: Raw plaintext password supplied by the user.
        user_id: The user's stable UUID, mixed in before hashing.

    Returns:
        A bcrypt hash string suitable for database storage.
    """
    peppered = (password + str(user_id)).encode()
    return bcrypt.hashpw(peppered, bcrypt.gensalt()).decode()


def verify_password(password: str, user_id: uuid.UUID, hashed: str) -> bool:
    """Verify a raw password against a stored bcrypt hash.

    Args:
        password: Raw plaintext password to verify.
        user_id: The user's stable UUID used as the pepper at hash time.
        hashed: The stored bcrypt hash string.

    Returns:
        True if the password matches, False otherwise.
    """
    peppered = (password + str(user_id)).encode()
    return bcrypt.checkpw(peppered, hashed.encode())


def create_access_token(user_id: uuid.UUID) -> str:
    """Create a signed JWT access token for a user.

    Args:
        user_id: The UUID of the authenticated user.

    Returns:
        A signed JWT string.
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> uuid.UUID | None:
    """Decode and validate a JWT access token.

    Args:
        token: The JWT string from the Authorization header.

    Returns:
        The user UUID if the token is valid and unexpired, else None.
    """
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return uuid.UUID(payload["sub"])
    except Exception:
        return None
