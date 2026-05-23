"""Event repository — persistence access for the events table.

All database queries for Event records live here.
Service and router layers must not build raw SQL or ORM queries
directly; they call this module instead.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.events import Event


def get_events(
    db: Session,
    *,
    city: str | None = None,
    state: str | None = None,
    status: str | None = None,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Event]:
    """Return a filtered, paginated list of events.

    Args:
        db: Active database session.
        city: Filter by city name (case-insensitive contains).
        state: Filter by exact state code or name.
        status: Filter by event status value.
        category: Filter by event category value.
        limit: Maximum number of rows to return.
        offset: Number of rows to skip (for pagination).

    Returns:
        A list of ``Event`` ORM instances.
    """
    stmt = select(Event)

    if city:
        stmt = stmt.where(Event.city.ilike(f"%{city}%"))
    if state:
        stmt = stmt.where(Event.state == state)
    if status:
        stmt = stmt.where(Event.status == status)
    if category:
        stmt = stmt.where(Event.category == category)

    stmt = stmt.order_by(Event.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def get_event_by_id(db: Session, event_id: uuid.UUID) -> Event | None:
    """Return a single event by its primary key, or None if not found.

    Args:
        db: Active database session.
        event_id: UUID primary key of the event.

    Returns:
        The matching ``Event`` instance or ``None``.
    """
    return db.get(Event, event_id)


def create_event(db: Session, **kwargs: Any) -> Event:
    """Insert a new event record and return it.

    Args:
        db: Active database session.
        **kwargs: Column values to set on the new event.

    Returns:
        The newly created ``Event`` instance (already added to the session).
    """
    event = Event(**kwargs)
    db.add(event)
    db.flush()
    return event


def update_event_status(db: Session, event: Event, new_status: str) -> Event:
    """Set the status field on an existing event and flush.

    Args:
        db: Active database session.
        event: The ``Event`` ORM instance to update.
        new_status: The new status string.

    Returns:
        The updated ``Event`` instance.
    """
    event.status = new_status
    db.flush()
    return event
