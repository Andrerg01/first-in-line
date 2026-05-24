"""SQLAlchemy model for the pipeline_tool_calls table."""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

_now = datetime.utcnow

class PipelineToolCall(Base):
    """One recorded tool call within a pipeline discovery run.

    Attributes:
        id: Primary key UUID.
        search_run_id: FK to the parent ``search_runs`` row.
        tool_name: Logical tool identifier (e.g. ``"web.search"``).
        input_summary: Truncated key input value (query or URL, ≤ 200 chars).
        outcome: Outcome code — ``success | error | timeout | rate_limit |
            duplicate | skipped``.
        duration_ms: Wall-clock duration of the call in milliseconds.
        http_status: HTTP response status from the MCP or backend server.
        error_message: Error detail when outcome is not ``"success"``.
        attempt_number: Retry attempt index (1-indexed).
        created_at: UTC timestamp inserted by the DB.
    """

    __tablename__ = "pipeline_tool_calls"

    id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4
    )
    search_run_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_name: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_number: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        server_default=text("now()"),
    )
