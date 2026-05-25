"""Event service — business logic for event retrieval.

Coordinates between the router layer and repository layer.  Any
cross-cutting concerns (validation, enrichment, filtering) live here
rather than in the router or repository.
"""

from __future__ import annotations

from datetime import date
import uuid

from fastapi import HTTPException
from fastapi import status as http_status
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
    status: list[str] | None = None,
    category: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radius_miles: float | None = None,
    geocoded_only: bool = False,
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
        start_date: Optional lower-bound event date filter.
        end_date: Optional upper-bound event date filter.
        lat: Optional center latitude for radius filtering.
        lon: Optional center longitude for radius filtering.
        radius_miles: Optional radius for geo filtering.
        geocoded_only: When true, return only events with lat/lon.
        limit: Page size, capped at 200.
        offset: Page offset.

    Returns:
        A list of ``Event`` instances.

    Raises:
        HTTPException: 422 when date or geo filter combinations are invalid.
    """
    limit = min(limit, 200)

    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start_date must be on or before end_date.",
        )

    if radius_miles is not None and (lat is None or lon is None):
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="lat and lon are required when radius_miles is provided.",
        )

    return event_repository.get_events(
        db,
        city=city,
        state=state,
        status=status,
        category=category,
        start_date=start_date,
        end_date=end_date,
        lat=lat,
        lon=lon,
        radius_miles=radius_miles,
        geocoded_only=geocoded_only,
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
            status_code=http_status.HTTP_404_NOT_FOUND,
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


def list_review_queue(
    db: Session,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[Event]:
    """Return candidate and needs_review events ordered by created_at descending.

    Args:
        db: Active database session.
        limit: Page size, capped at 200.
        offset: Pagination offset.

    Returns:
        A list of ``Event`` instances awaiting review.
    """
    limit = min(limit, 200)
    return event_repository.get_review_queue_events(db, limit=limit, offset=offset)
