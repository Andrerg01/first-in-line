"""Unit test conftest — shared fixtures for unit tests.

Provides an in-memory SQLite session for repository and service unit tests.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, override_engine

# Map every named schema to None so SQLite (which has no schema support) can
# create tables without schema prefixes.
_SCHEMA_TRANSLATE: dict[str, None] = {
    "events": None,
    "ingestion": None,
    "users": None,
    "logs": None,
}


@pytest.fixture(scope="function")
def db_session():
    """Yield a fresh SQLite in-memory session for each unit test.

    Creates all tables before the test and drops them after.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    ).execution_options(schema_translate_map=_SCHEMA_TRANSLATE)
    override_engine(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
