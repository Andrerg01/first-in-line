"""Event service — business logic for event retrieval.

Coordinates between the router layer and repository layer.  Any
cross-cutting concerns (validation, enrichment, filtering) live here
rather than in the router or repository.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.claims import EventClaim
from app.models.events import Event
from app.models.sources import EventSource
from app.repositories import claims_repository, event_repository, source_repository


def list_events(
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
        city: Optional city name filter (partial match).
        state: Optional state filter (exact match).
        status: Optional event status filter.
        category: Optional category filter.
        limit: Page size, capped at 200.
        offset: Page offset.

    Returns:
        A list of ``Event`` instances.
    """
    limit = min(limit, 200)
    return event_repository.get_events(
        db,
        city=city,
        state=state,
        status=status,
        category=category,
        limit=limit,
        offset=offset,
    )


def get_event_detail(db: Session, event_id: uuid.UUID) -> Event:
    """Return a single event or raise 404.

    Args:
        db: Active database session.
        event_id: UUID of the requested event.

    Returns:
        The matching ``Event`` instance.

    Raises:
        HTTPException: 404 if the event does not exist.
    """
    event = event_repository.get_event_by_id(db, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found.",
        )
    return event


def get_event_sources(db: Session, event_id: uuid.UUID) -> list[EventSource]:
    """Return source documents for an event, verifying the event exists first.

    Args:
        db: Active database session.
        event_id: UUID of the event.

    Returns:
        A list of ``EventSource`` join records with source documents loaded.

    Raises:
        HTTPException: 404 if the event does not exist.
    """
    get_event_detail(db, event_id)  # raises 404 if missing
    return source_repository.get_sources_for_event(db, event_id)


def get_event_claims(db: Session, event_id: uuid.UUID) -> list[EventClaim]:
    """Return extracted claims for an event, verifying the event exists first.

    Args:
        db: Active database session.
        event_id: UUID of the event.

    Returns:
        A list of ``EventClaim`` instances.

    Raises:
        HTTPException: 404 if the event does not exist.
    """
    get_event_detail(db, event_id)  # raises 404 if missing
    return claims_repository.get_claims_for_event(db, event_id)


def patch_event_status(db: Session, event_id: uuid.UUID, new_status: str) -> Event:
    """Update the status of an event.

    Args:
        db: Active database session.
        event_id: UUID of the event to update.
        new_status: The desired status value.

    Returns:
        The updated ``Event`` instance.

    Raises:
        HTTPException: 404 if the event does not exist.
    """
    event = get_event_detail(db, event_id)  # raises 404 if missing
    return event_repository.update_event_status(db, event, new_status)
