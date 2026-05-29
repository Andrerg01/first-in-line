"""LLMCall ORM model.

Records every OpenAI API call made during the extraction pipeline so
token usage, cost, and latency can be audited per run.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.processing import ProcessingDecision


def _now() -> datetime:
    return datetime.now(timezone.utc)


class LLMCall(Base):
    """A single OpenAI API call recorded during extraction."""

    __tablename__ = "llm_calls"
    __table_args__ = {"schema": "logs"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    call_type: Mapped[str] = mapped_column(
        String(60), nullable=False
    )  # classify_relevance | classify_event_count | extract_event | extract_multi_event
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="success"
    )  # success | error
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    processing_decisions: Mapped[list[ProcessingDecision]] = relationship(
        "ProcessingDecision", back_populates="llm_call"
    )
