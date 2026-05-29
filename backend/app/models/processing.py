"""Processing decision ORM model.

Records important automated decisions made during the ingestion
pipeline so the system remains auditable and reviewable.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.events import Event
    from app.models.llm_calls import LLMCall
    from app.models.sources import SourceDocument


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ProcessingDecision(Base):
    """An automated decision recorded during ingestion for auditability."""

    __tablename__ = "processing_decisions"
    __table_args__ = {"schema": "logs"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ingestion.source_documents.id", ondelete="SET NULL"), nullable=True
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("events.events.id", ondelete="SET NULL"), nullable=True
    )
    decision_type: Mapped[str] = mapped_column(String(60), nullable=False)
    decision_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    llm_call_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("logs.llm_calls.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    source_document: Mapped[SourceDocument | None] = relationship(
        "SourceDocument", back_populates="processing_decisions"
    )
    event: Mapped[Event | None] = relationship(
        "Event", back_populates="processing_decisions"
    )
    llm_call: Mapped[LLMCall | None] = relationship(
        "LLMCall", back_populates="processing_decisions"
    )
