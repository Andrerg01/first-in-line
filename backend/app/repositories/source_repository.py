"""Source repository — persistence access for source_documents and event_sources.

All database queries for SourceDocument and EventSource records live here.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.sources import EventSource, SourceDocument


def get_sources_for_event(db: Session, event_id: uuid.UUID) -> list[EventSource]:
    """Return all event-source join records for a given event, with source documents eager-loaded.

    Args:
        db: Active database session.
        event_id: UUID of the event whose sources to retrieve.

    Returns:
        A list of ``EventSource`` instances with ``source_document`` loaded.
    """
    stmt = (
        select(EventSource)
        .where(EventSource.event_id == event_id)
        .options(joinedload(EventSource.source_document))
        .order_by(EventSource.created_at.asc())
    )
    return list(db.scalars(stmt).unique().all())


def get_source_document_by_id(
    db: Session, source_id: uuid.UUID
) -> SourceDocument | None:
    """Return a source document by primary key, or None.

    Args:
        db: Active database session.
        source_id: UUID primary key of the source document.

    Returns:
        The matching ``SourceDocument`` or ``None``.
    """
    return db.get(SourceDocument, source_id)


def find_source_by_hash(db: Session, text_hash: str | None) -> SourceDocument | None:
    """Look up a source document by its visible-text hash for deduplication.

    Returns ``None`` immediately when ``text_hash`` is ``None`` or empty,
    because SQL ``WHERE col = NULL`` is always false and the explicit guard
    makes the intent clear.

    Args:
        db: Active database session.
        text_hash: SHA-256 hex digest of the page's normalised visible text.

    Returns:
        The matching ``SourceDocument`` or ``None``.
    """
    if not text_hash:
        return None
    stmt = select(SourceDocument).where(SourceDocument.visible_text_hash == text_hash)
    return db.scalars(stmt).first()


def get_event_source_for_source_document(
    db: Session, source_document_id: uuid.UUID
) -> EventSource | None:
    """Return the first EventSource linking this source document to an event.

    Args:
        db: Active database session.
        source_document_id: UUID of the source document.

    Returns:
        The matching ``EventSource`` or ``None`` if none exists.
    """
    stmt = (
        select(EventSource)
        .where(EventSource.source_document_id == source_document_id)
        .limit(1)
    )
    return db.scalars(stmt).first()


def create_source_document(db: Session, **kwargs: Any) -> SourceDocument:
    """Insert a new source document and return it.

    Args:
        db: Active database session.
        **kwargs: Column values for the new source document.

    Returns:
        The newly created ``SourceDocument``.
    """
    doc = SourceDocument(**kwargs)
    db.add(doc)
    db.flush()
    return doc


def create_event_source(
    db: Session,
    event_id: uuid.UUID,
    source_document_id: uuid.UUID,
    relationship_type: str = "primary_source",
) -> EventSource:
    """Create an event-source link between an event and a source document.

    Args:
        db: Active database session.
        event_id: UUID of the event.
        source_document_id: UUID of the source document.
        relationship_type: Semantic relationship (e.g. ``"primary_source"``).

    Returns:
        The newly created ``EventSource``.
    """
    link = EventSource(
        event_id=event_id,
        source_document_id=source_document_id,
        relationship_type=relationship_type,
    )
    db.add(link)
    db.flush()
    return link
