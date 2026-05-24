"""Admin router — HTTP handlers for the /api/admin endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.events import EventListItem
from app.services import event_service

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
