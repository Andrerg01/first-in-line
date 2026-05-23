"""Events router — HTTP handlers for the /api/events endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.claims import EventClaimResponse
from app.schemas.events import EventDetail, EventListItem, EventStatusUpdate
from app.schemas.sources import EventSourceResponse
from app.services import event_service

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=list[EventListItem])
def list_events(
    city: str | None = Query(None, description="Filter by city (partial match)"),
    state: str | None = Query(None, description="Filter by state"),
    status: str | None = Query(None, description="Filter by event status"),
    category: str | None = Query(None, description="Filter by event category"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
) -> list[EventListItem]:
    """Return a paginated, filterable list of events."""
    events = event_service.list_events(
        db,
        city=city,
        state=state,
        status=status,
        category=category,
        limit=limit,
        offset=offset,
    )
    return [EventListItem.model_validate(e) for e in events]


@router.get("/{event_id}", response_model=EventDetail)
def get_event(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> EventDetail:
    """Return the full detail for a single event."""
    event = event_service.get_event_detail(db, event_id)
    return EventDetail.model_validate(event)


@router.get("/{event_id}/sources", response_model=list[EventSourceResponse])
def get_event_sources(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[EventSourceResponse]:
    """Return source documents associated with an event."""
    sources = event_service.get_event_sources(db, event_id)
    return [EventSourceResponse.model_validate(s) for s in sources]


@router.get("/{event_id}/claims", response_model=list[EventClaimResponse])
def get_event_claims(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[EventClaimResponse]:
    """Return extracted claims associated with an event."""
    claims = event_service.get_event_claims(db, event_id)
    return [EventClaimResponse.model_validate(c) for c in claims]


@router.patch("/{event_id}/status", response_model=EventDetail)
def patch_event_status(
    event_id: uuid.UUID,
    body: EventStatusUpdate,
    db: Session = Depends(get_db),
) -> EventDetail:
    """Update the status of an event (verify, reject, etc.)."""
    event = event_service.patch_event_status(db, event_id, body.status)
    db.commit()
    db.refresh(event)
    return EventDetail.model_validate(event)
