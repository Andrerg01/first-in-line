"""Dedup repository — queries for finding and flagging duplicate events.

All raw ORM queries for duplicate detection live here.  Service and
router layers must not build raw SQL or ORM queries directly.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.events import Event
from app.utils.dedup_location import normalize_location_value


def find_candidates_by_city_state(
    db: Session,
    *,
    city: str | None,
    state: str | None,
    exclude_id: uuid.UUID,
    statuses: tuple[str, ...] = ("candidate", "verified", "needs_review"),
    limit: int = 50,
) -> list[Event]:
    """Return non-merged events in the same city/state for similarity scoring.

    Args:
        db: Active database session.
        city: City to match (case-insensitive).
        state: State to match exactly.
        exclude_id: The event ID being evaluated — excluded from results.
        statuses: Only return events with these status values.
        limit: Maximum number of rows to return.

    Returns:
        A list of ``Event`` instances that could be duplicates.
    """
    stmt = select(Event).where(Event.id != exclude_id, Event.status.in_(statuses))
    city = normalize_location_value(city)
    state = normalize_location_value(state)
    if city:
        stmt = stmt.where(func.lower(func.trim(Event.city)).like(f"%{city}%"))
    if state:
        stmt = stmt.where(func.lower(func.trim(Event.state)) == state)
    stmt = stmt.order_by(Event.created_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())


def set_duplicate_flag(
    db: Session,
    event: Event,
    *,
    duplicate_of_id: uuid.UUID | None,
) -> Event:
    """Mark an event as a possible duplicate and record the suspect canonical.

    Args:
        db: Active database session.
        event: The ``Event`` to flag.
        duplicate_of_id: Primary key of the suspected canonical event, or
            ``None`` to clear the flag.

    Returns:
        The updated ``Event`` instance.
    """
    event.possible_duplicate = duplicate_of_id is not None
    event.duplicate_of_id = duplicate_of_id
    db.flush()
    return event


def get_event_with_claims(db: Session, event_id: uuid.UUID) -> Event | None:
    """Load an event and eagerly load its claims.

    Args:
        db: Active database session.
        event_id: UUID primary key.

    Returns:
        The ``Event`` instance with ``claims`` loaded, or ``None``.
    """
    from sqlalchemy.orm import selectinload

    stmt = (
        select(Event)
        .options(selectinload(Event.claims))
        .where(Event.id == event_id)
    )
    return db.scalars(stmt).first()


def set_normalized_name(
    db: Session,
    event: Event,
    normalized: str | None,
) -> Event:
    """Persist the normalized business name on an event record.

    Args:
        db: Active database session.
        event: The ``Event`` to update.
        normalized: The pre-computed normalized name string.

    Returns:
        The updated ``Event`` instance.
    """
    event.normalized_business_name = normalized
    db.flush()
    return event


def list_events_for_retroactive_scan(
    db: Session,
    *,
    statuses: tuple[str, ...] = ("candidate", "verified", "needs_review"),
) -> list[Event]:
    """Return existing events in canonical scan order for retroactive dedup.

    Args:
        db: Active database session.
        statuses: Event statuses eligible for duplicate scanning.

    Returns:
        A list of ``Event`` rows ordered oldest-first, then by ID.
    """
    stmt = (
        select(Event)
        .where(Event.status.in_(statuses))
        .order_by(Event.created_at.asc(), Event.id.asc())
    )
    return list(db.scalars(stmt).all())
