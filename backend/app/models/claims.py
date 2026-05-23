"""Event claims ORM model.

Stores atomic extracted claims from source documents.  One claim
represents one piece of structured information (e.g. event_date,
business_name) extracted from a specific source.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.events import Event
    from app.models.sources import SourceDocument


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EventClaim(Base):
    """An atomic extracted claim from a source document."""

    __tablename__ = "event_claims"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"), nullable=True
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False
    )
    claim_type: Mapped[str] = mapped_column(
        String(40), nullable=False
    )  # business_name | event_date | address | city | state | promotion | event_type | category | opening_status
    claim_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    claim_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    event: Mapped[Event | None] = relationship("Event", back_populates="claims")
    source_document: Mapped[SourceDocument] = relationship(
        "SourceDocument", back_populates="claims"
    )
