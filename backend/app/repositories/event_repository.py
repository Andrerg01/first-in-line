"""Event repository — persistence access for the events table.

All database queries for Event records live here.
Service and router layers must not build raw SQL or ORM queries
directly; they call this module instead.
"""

from __future__ import annotations

from datetime import date
import uuid
from typing import Any

from math import atan2, cos, radians, sin, sqrt
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.events import Event


def get_events(
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
        city: Filter by city name (case-insensitive contains).
        state: Filter by exact state code or name.
        status: Filter by event status value.
        category: Filter by event category value.
        start_date: Filter to events on or after this date.
        end_date: Filter to events on or before this date.
        lat: Center latitude used for radius filtering.
        lon: Center longitude used for radius filtering.
        radius_miles: Radius used for distance filtering.
        geocoded_only: When true, include only events with lat/lon.
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
        stmt = stmt.where(Event.status.in_(status))
    if category:
        stmt = stmt.where(Event.category.in_(category))
    if start_date or end_date:
        # An event matches if any of its date representations overlap [start_date, end_date].
        # Range overlap: date_range_end >= start_date AND date_range_start <= end_date.
        # Exact fallback: event_date falls within [start_date, end_date].
        if start_date and end_date:
            range_overlap = and_(
                or_(Event.date_range_end.is_(None), Event.date_range_end >= start_date),
                or_(Event.date_range_start.is_(None), Event.date_range_start <= end_date),
                Event.date_range_start.is_not(None),
            )
            exact_match = and_(
                Event.event_date >= start_date,
                Event.event_date <= end_date,
            )
            stmt = stmt.where(or_(range_overlap, exact_match))
        elif start_date:
            stmt = stmt.where(
                or_(
                    and_(Event.date_range_end.is_not(None), Event.date_range_end >= start_date),
                    and_(Event.date_range_end.is_(None), Event.event_date >= start_date),
                )
            )
        else:  # end_date only
            stmt = stmt.where(
                or_(
                    and_(Event.date_range_start.is_not(None), Event.date_range_start <= end_date),
                    and_(Event.date_range_start.is_(None), Event.event_date <= end_date),
                )
            )

    should_require_geocoded = geocoded_only or radius_miles is not None
    if should_require_geocoded:
        stmt = stmt.where(Event.lat.is_not(None), Event.lon.is_not(None))

    ordered_stmt = stmt.order_by(Event.created_at.desc())

    if radius_miles is None:
        paged_stmt = ordered_stmt.limit(limit).offset(offset)
        return list(db.scalars(paged_stmt).all())

    events = list(db.scalars(ordered_stmt).all())
    filtered = [
        event
        for event in events
        if _distance_miles(
            lat,
            lon,
            float(event.lat),
            float(event.lon),
        )
        <= radius_miles
    ]
    return filtered[offset : offset + limit]


def _distance_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance between two points in miles."""
    earth_radius_miles = 3958.8

    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)

    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad

    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    )
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return earth_radius_miles * c


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


def get_review_queue_events(
    db: Session,
    *,
    statuses: tuple[str, ...] = ("candidate", "needs_review"),
    limit: int = 50,
    offset: int = 0,
) -> list[Event]:
    """Return one globally ordered review queue page across multiple statuses.

    Args:
        db: Active database session.
        statuses: Statuses included in the queue.
        limit: Maximum number of rows to return.
        offset: Number of rows to skip in the globally ordered queue.

    Returns:
        A list of ``Event`` ORM instances ordered by created_at descending.
    """
    stmt = (
        select(Event)
        .where(Event.status.in_(statuses))
        .order_by(Event.created_at.desc(), Event.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt).all())


def list_events_pointing_to_duplicate_target(
    db: Session,
    duplicate_of_id: uuid.UUID,
) -> list[Event]:
    """Return events currently pointing at the supplied duplicate target.

    Args:
        db: Active database session.
        duplicate_of_id: Duplicate target to match.

    Returns:
        A list of ``Event`` instances whose ``duplicate_of_id`` matches.
    """
    stmt = select(Event).where(Event.duplicate_of_id == duplicate_of_id)
    return list(db.scalars(stmt).all())


def update_event_geo(
    db: Session,
    event: Event,
    *,
    lat: float,
    lon: float,
) -> Event:
    """Update the lat/lon coordinates on an event and flush.

    Args:
        db: Active database session.
        event: The ``Event`` ORM instance to update.
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.

    Returns:
        The updated ``Event`` instance.
    """
    event.lat = lat
    event.lon = lon
    db.flush()
    return event


def get_ungeocoded_events(db: Session, *, limit: int = 500) -> list[Event]:
    """Return events that have address information but no lat/lon.

    Args:
        db: Active database session.
        limit: Maximum number of events to return.

    Returns:
        A list of ``Event`` instances without geocoordinates.
    """
    stmt = (
        select(Event)
        .where(
            Event.lat.is_(None),
            (Event.address.is_not(None)) | (Event.city.is_not(None)),
        )
        .order_by(Event.created_at.asc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())
