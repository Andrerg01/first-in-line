"""Source document and event-source ORM models.

source_documents — fetched and normalised web page content.
event_sources — many-to-many join between events and source documents.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.claims import EventClaim
    from app.models.events import Event
    from app.models.processing import ProcessingDecision


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SourceDocument(Base):
    """A fetched and normalised web page."""

    __tablename__ = "source_documents"
    __table_args__ = (
        UniqueConstraint("visible_text_hash", name="uq_source_documents_text_hash"),
        Index("ix_source_documents_canonical_url", "canonical_url"),
        Index("ix_source_documents_domain", "domain"),
        Index("ix_source_documents_fetched_at", "fetched_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    visible_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    visible_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fetch_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # success | failed | skipped
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    fetch_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    event_sources: Mapped[list[EventSource]] = relationship(
        "EventSource", back_populates="source_document", cascade="all, delete-orphan"
    )
    claims: Mapped[list[EventClaim]] = relationship(
        "EventClaim", back_populates="source_document"
    )
    processing_decisions: Mapped[list[ProcessingDecision]] = relationship(
        "ProcessingDecision", back_populates="source_document"
    )


class EventSource(Base):
    """Join record linking an event to one of its source documents."""

    __tablename__ = "event_sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(
        String(40), nullable=False, default="primary_source"
    )  # primary_source | supporting_source | conflicting_source | rejected_source
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    event: Mapped[Event] = relationship(
        "Event", back_populates="event_sources"
    )
    source_document: Mapped[SourceDocument] = relationship(
        "SourceDocument", back_populates="event_sources"
    )


# Avoid circular import — EventClaim and ProcessingDecision are defined in their own modules.
from app.models.claims import EventClaim  # noqa: E402, F401
from app.models.events import Event  # noqa: E402, F401
from app.models.processing import ProcessingDecision  # noqa: E402, F401
