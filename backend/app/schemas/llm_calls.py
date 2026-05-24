"""Pydantic schemas for LLM call records."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LLMCallCreate(BaseModel):
    """Payload the worker sends when logging a single LLM API call."""

    call_type: str = Field(
        ...,
        description=(
            "classify_relevance | classify_event_count | "
            "extract_event | extract_multi_event"
        ),
    )
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    latency_ms: int | None = None
    status: Literal["success", "error"] = "success"
    error_message: str | None = None


class LLMCallOut(BaseModel):
    """API response shape for an LLM call record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    call_type: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    cost_usd: float | None
    latency_ms: int | None
    status: str
    error_message: str | None
    created_at: datetime
