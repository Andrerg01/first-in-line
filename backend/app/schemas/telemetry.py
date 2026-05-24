"""Pydantic schemas for pipeline telemetry endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


OutcomeCode = Literal[
    "success", "error", "timeout", "rate_limit", "duplicate", "skipped"
]


class ToolCallCreate(BaseModel):
    """One tool call record sent from the worker to the backend."""

    tool_name: str = Field(..., max_length=60)
    input_summary: str | None = Field(default=None, max_length=200)
    outcome: OutcomeCode
    duration_ms: int | None = Field(default=None, ge=0)
    http_status: int | None = None
    error_message: str | None = None
    attempt_number: int = Field(default=1, ge=1)


class ToolCallsBulkCreate(BaseModel):
    """Bulk payload for POST /api/ingest/search-run/{run_id}/tool-calls."""

    tool_calls: list[ToolCallCreate]


class ToolCallOut(BaseModel):
    """Response schema for a persisted tool call record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    search_run_id: uuid.UUID
    tool_name: str
    input_summary: str | None
    outcome: str
    duration_ms: int | None
    http_status: int | None
    error_message: str | None
    attempt_number: int
    created_at: datetime


class RunStatsUpdate(BaseModel):
    """Aggregate run stats included in the finish-run PATCH payload."""

    queries_executed: int | None = None
    search_results_found: int | None = None
    urls_attempted: int | None = None
    source_docs_created: int | None = None
    source_docs_skipped: int | None = None
    fetch_errors: int | None = None
    elapsed_seconds: float | None = None
