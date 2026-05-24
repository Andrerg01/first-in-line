"""Event ORM model.

Stores canonical event records that represent a business grand opening
or similar event.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.claims import EventClaim
    from app.models.processing import ProcessingDecision
    from app.models.sources import EventSource


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Event(Base):
    """A canonical grand-opening (or similar) event record."""

    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_event_date", "event_date"),
        Index("ix_events_city_state", "city", "state"),
        Index("ix_events_status", "status"),
        Index("ix_events_business_name", "business_name"),
        Index("ix_events_possible_duplicate", "possible_duplicate"),
        Index("ix_events_normalized_business_name", "normalized_business_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(
        String(40), nullable=False, default="unknown"
    )  # grand_opening | soft_opening | ribbon_cutting | reopening | anniversary | unknown
    category: Mapped[str | None] = mapped_column(
        String(60), nullable=True
    )  # restaurant | cafe | food_truck | brewery | retail | other
    event_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(60), nullable=True)
    country: Mapped[str | None] = mapped_column(String(60), nullable=True, default="US")
    lat: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    lon: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    promotion_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="candidate"
    )  # candidate | verified | rejected | needs_review | merged | expired
    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    possible_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"), nullable=True
    )
    normalized_business_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    event_sources: Mapped[list[EventSource]] = relationship(
        "EventSource", back_populates="event", cascade="all, delete-orphan"
    )
    claims: Mapped[list[EventClaim]] = relationship(
        "EventClaim", back_populates="event"
    )
    processing_decisions: Mapped[list[ProcessingDecision]] = relationship(
        "ProcessingDecision", back_populates="event"
    )
