"""Repository for pipeline_tool_calls persistence."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.telemetry import PipelineToolCall


def bulk_insert_tool_calls(
    db: Session,
    search_run_id: uuid.UUID,
    records: list[dict[str, Any]],
) -> int:
    """Bulk-insert tool call records for a search run.

    Args:
        db: Active database session.
        search_run_id: UUID of the parent search run.
        records: List of dicts with keys: tool_name, input_summary, outcome,
            duration_ms, http_status, error_message, attempt_number.

    Returns:
        Number of rows inserted.
    """
    rows = [
        PipelineToolCall(
            search_run_id=search_run_id,
            tool_name=r["tool_name"],
            input_summary=r.get("input_summary"),
            outcome=r["outcome"],
            duration_ms=r.get("duration_ms"),
            http_status=r.get("http_status"),
            error_message=r.get("error_message"),
            attempt_number=r.get("attempt_number", 1),
        )
        for r in records
    ]
    db.add_all(rows)
    db.flush()
    return len(rows)


def get_tool_calls_for_run(
    db: Session,
    search_run_id: uuid.UUID,
) -> list[PipelineToolCall]:
    """Return all tool call records for a given search run.

    Args:
        db: Active database session.
        search_run_id: UUID of the parent search run.

    Returns:
        List of ``PipelineToolCall`` ORM objects ordered by creation time.
    """
    return (
        db.query(PipelineToolCall)
        .filter(PipelineToolCall.search_run_id == search_run_id)
        .order_by(PipelineToolCall.created_at)
        .all()
    )
