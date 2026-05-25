"""Admin router — HTTP handlers for the /api/admin endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.admin import (
    ConflictsResponse,
    ConflictSide,
    DuplicateFlagRequest,
    DuplicateFlagResponse,
    MergeRequest,
    MergeResponse,
    RetroactiveDedupResponse,
)
from app.schemas.events import EventListItem
from app.services import dedup_service, event_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/review-queue", response_model=list[EventListItem])
def get_review_queue(
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
) -> list[EventListItem]:
    """Return candidate events awaiting human review, newest first.

    Only events with status ``candidate`` or ``needs_review`` are included.
    Used by the admin review queue page in the frontend.

    Args:
        limit: Maximum number of events to return.
        offset: Pagination offset.
        db: Injected database session.

    Returns:
        A list of ``EventListItem`` schemas ordered by created_at descending.
    """
    events = event_service.list_review_queue(db, limit=limit, offset=offset)
    return [EventListItem.model_validate(e) for e in events]


@router.get("/events/{event_id}/conflicts", response_model=ConflictsResponse)
def get_event_conflicts(
    event_id: uuid.UUID,
    other_id: uuid.UUID = Query(..., description="UUID of the other event to compare"),
    db: Session = Depends(get_db),
) -> ConflictsResponse:
    """Return a side-by-side claim comparison between two events.

    Args:
        event_id: UUID of the first event (typically the candidate/duplicate).
        other_id: UUID of the second event (typically the canonical).
        db: Injected database session.

    Returns:
        ``ConflictsResponse`` with both events' claims and conflicting types.
    """
    try:
        data = dedup_service.get_conflicts(db, event_id, other_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ConflictsResponse(
        event_a=ConflictSide(
            id=event_id,
            business_name=data["event_a"]["business_name"],
            claims=data["event_a"]["claims"],
        ),
        event_b=ConflictSide(
            id=other_id,
            business_name=data["event_b"]["business_name"],
            claims=data["event_b"]["claims"],
        ),
        conflicting_claim_types=data["conflicting_claim_types"],
    )


@router.post("/events/{event_id}/flag-duplicate", response_model=DuplicateFlagResponse)
def flag_event_as_duplicate(
    event_id: uuid.UUID,
    body: DuplicateFlagRequest,
    db: Session = Depends(get_db),
) -> DuplicateFlagResponse:
    """Manually flag or unflag an event as a possible duplicate.

    Pass ``duplicate_of_id`` to flag, or ``null`` to clear the flag.

    Args:
        event_id: UUID of the event to update.
        body: ``DuplicateFlagRequest`` with optional ``duplicate_of_id``.
        db: Injected database session.

    Returns:
        ``DuplicateFlagResponse`` with updated flag state.
    """
    try:
        event = dedup_service.flag_duplicate(
            db,
            event_id=event_id,
            duplicate_of_id=body.duplicate_of_id,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 422 if "must differ" in detail or "not a canonical root" in detail else 404
        raise HTTPException(status_code=status_code, detail=detail) from exc

    db.commit()

    action = "flagged" if body.duplicate_of_id else "cleared"
    return DuplicateFlagResponse(
        id=event.id,
        possible_duplicate=event.possible_duplicate,
        duplicate_of_id=event.duplicate_of_id,
        message=f"Duplicate flag {action}.",
    )


@router.post("/events/{event_id}/merge", response_model=MergeResponse)
def merge_events(
    event_id: uuid.UUID,
    body: MergeRequest,
    db: Session = Depends(get_db),
) -> MergeResponse:
    """Merge a source event into a canonical target event.

    The source event is re-classified as ``merged`` and its claims are
    re-assigned to the target event.  Optional ``canonical_fields`` override
    specific field values on the target.

    Args:
        body: ``MergeRequest`` with source_id, target_id, and optional
            canonical_fields overrides.
        db: Injected database session.

    Returns:
        ``MergeResponse`` representing the updated canonical (target) event.
    """
    try:
        canonical = dedup_service.merge_events(
            db,
            source_id=event_id,
            target_id=body.target_id,
            canonical_fields=body.canonical_fields.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 422 if "must differ" in detail or "not a canonical root" in detail else 404
        raise HTTPException(status_code=status_code, detail=detail) from exc

    db.commit()

    return MergeResponse(
        id=canonical.id,
        business_name=canonical.business_name,
        status=canonical.status,
        updated_at=canonical.updated_at,
        message="Merge completed.",
    )


@router.post("/dedup/retroactive-run", response_model=RetroactiveDedupResponse)
def run_retroactive_dedup(db: Session = Depends(get_db)) -> RetroactiveDedupResponse:
    """Run duplicate detection across existing events on demand."""
    result = dedup_service.run_retroactive_scan(db)
    db.commit()
    return RetroactiveDedupResponse(
        scanned=result["scanned"],
        flagged=result["flagged"],
        cleared=result["cleared"],
        message="Retroactive duplicate scan completed.",
    )


@router.post("/geocode/run")
def run_bulk_geocode(db: Session = Depends(get_db)) -> dict:
    """Geocode all events that are missing lat/lon coordinates.

    Scans events with address/city information but no geocoordinates and
    calls the MCP ``geo.geocode_address`` tool for each one.  The operation
    is best-effort: individual geocode failures do not abort the run.

    Args:
        db: Injected database session.

    Returns:
        Dict with ``attempted``, ``geocoded``, and ``skipped`` counts.
    """
    from app.services import geocode_service  # local import avoids circular
    return geocode_service.geocode_ungeocoded_events(db)

