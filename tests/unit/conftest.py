"""Unit test conftest — shared fixtures for unit tests.

Provides an in-memory SQLite session for repository and service unit tests.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, override_engine


@pytest.fixture(scope="function")
def db_session():
    """Yield a fresh SQLite in-memory session for each unit test.

    Creates all tables before the test and drops them after.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    override_engine(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
