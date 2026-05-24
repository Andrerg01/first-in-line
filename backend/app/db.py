"""Database engine and session factory.

Provides a SQLAlchemy engine and a session generator for use as a
FastAPI dependency.  All modules that need database access import
``get_db`` from here rather than constructing sessions directly.

The engine is built lazily on first access so that importing this module
in test contexts (where ``DATABASE_URL`` may be overridden) does not
fail at import time.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Callable

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


_engine: Engine | None = None
_session_factory: Callable[[], Session] | None = None


def _get_engine() -> Engine:
    """Return the cached engine, building it on first call.

    Returns:
        A configured SQLAlchemy ``Engine`` instance.

    Raises:
        ValueError: If ``DATABASE_URL`` is empty.
    """
    global _engine
    if _engine is None:
        url = settings.database_url
        if not url:
            raise ValueError(
                "DATABASE_URL is not set; cannot initialise database engine."
            )
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def _get_session_factory() -> Callable[[], Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            autocommit=False, autoflush=False, bind=_get_engine()
        )
    return _session_factory


def override_engine(engine: Engine) -> None:
    """Replace the module-level engine and session factory.

    Intended for use in tests only — call this before the first request.

    Args:
        engine: A pre-configured SQLAlchemy engine (e.g. SQLite in-memory).
    """
    global _engine, _session_factory
    _engine = engine
    _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and ensure it is closed afterward.

    Intended for use as a FastAPI dependency::

        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...

    Yields:
        An active ``sqlalchemy.orm.Session``.
    """
    factory = _get_session_factory()
    db = factory()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
