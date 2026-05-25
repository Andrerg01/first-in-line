"""Pydantic schemas for the LangGraph extraction pipeline.

These are worker-side schemas validated against raw LLM output before any
data is forwarded to the backend API.  They mirror the backend's ingest
schemas but live in the worker so the extraction package has no runtime
dependency on backend code.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# LLM call tracking (worker-side; mirrored by backend LLMCallCreate)
# ---------------------------------------------------------------------------


class LLMCallData(BaseModel):
    """Timing and token data for a single LLM API call.

    Accumulated in ExtractionState and forwarded to the backend
    ``POST /api/ingest/source-document/{id}/candidate`` payload.
    """

    call_type: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    latency_ms: int | None = None
    status: Literal["success", "error"] = "success"
    error_message: str | None = None


# ---------------------------------------------------------------------------
# Relevance classification
# ---------------------------------------------------------------------------


class RelevanceResult(BaseModel):
    """Output schema for the classify_relevance LLM call."""

    is_relevant: bool
    reason: str | None = None


# ---------------------------------------------------------------------------
# Event-count classification
# ---------------------------------------------------------------------------


class EventCountResult(BaseModel):
    """Output schema for the classify_event_count LLM call."""

    event_count: Literal["single", "multi", "none"]
    count_estimate: int = Field(default=1, ge=0, le=50)
    reason: str | None = None


# ---------------------------------------------------------------------------
# Single event extraction
# ---------------------------------------------------------------------------


class ExtractedClaim(BaseModel):
    """A single extracted claim from an event page."""

    claim_type: Literal[
        "business_name",
        "event_date",
        "address",
        "city",
        "state",
        "promotion",
        "event_type",
        "category",
        "opening_status",
    ]
    claim_value: str
    claim_text: str | None = None


class ExtractedEvent(BaseModel):
    """A single structured event extracted from page text."""

    business_name: str | None = None
    event_name: str | None = None
    event_type: Literal[
        "grand_opening",
        "soft_opening",
        "ribbon_cutting",
        "reopening",
        "anniversary",
        "unknown",
    ] = "unknown"
    category: Literal[
        "restaurant", "cafe", "food_truck", "brewery", "retail", "other", None
    ] = None
    event_date_str: str | None = None
    date_confidence: Literal["exact", "month", "season", "year", "unknown"] = "unknown"
    date_range_start: str | None = None
    date_range_end: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    promotion_text: str | None = None
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    claims: list[ExtractedClaim] = []


class SingleEventExtractionResult(BaseModel):
    """Validated output for the extract_event LLM call (single-event path)."""

    event: ExtractedEvent


class MultiEventExtractionResult(BaseModel):
    """Validated output for the extract_multi_event LLM call.

    One source document may contain multiple distinct business openings
    (e.g. a news roundup article).  Each entry produces its own candidate
    event record linked to the same source_document_id.
    """

    events: list[ExtractedEvent] = []
