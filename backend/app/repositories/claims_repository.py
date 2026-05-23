"""Claims repository — persistence access for the event_claims table."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.claims import EventClaim


def get_claims_for_event(db: Session, event_id: uuid.UUID) -> list[EventClaim]:
    """Return all claims associated with a given event.

    Args:
        db: Active database session.
        event_id: UUID of the event whose claims to retrieve.

    Returns:
        A list of ``EventClaim`` instances ordered by creation time.
    """
    stmt = (
        select(EventClaim)
        .where(EventClaim.event_id == event_id)
        .order_by(EventClaim.created_at.asc())
    )
    return list(db.scalars(stmt).all())


def create_claim(db: Session, **kwargs: Any) -> EventClaim:
    """Insert a new event claim and return it.

    Args:
        db: Active database session.
        **kwargs: Column values for the new claim.

    Returns:
        The newly created ``EventClaim``.
    """
    claim = EventClaim(**kwargs)
    db.add(claim)
    db.flush()
    return claim
