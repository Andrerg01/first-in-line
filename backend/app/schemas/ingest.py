"""Pydantic schemas for the manual URL ingestion endpoint."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.llm_calls import LLMCallCreate


class ManualIngestRequest(BaseModel):
    """Request body for POST /api/ingest/manual-url."""

    url: str

    @field_validator("url")
    @classmethod
    def validate_http_url(cls, v: str) -> str:
        """Reject non-HTTP/S schemes as a defence-in-depth measure against SSRF."""
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Only http and https URLs are accepted.")
        if not parsed.netloc:
            raise ValueError("URL must include a valid host.")
        return v


class LLMClaim(BaseModel):
    """A single extracted claim from the LLM JSON output."""

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
    claim_text: str


class LLMExtractionResult(BaseModel):
    """Validated output from the OpenAI extraction call.

    This model is applied before any data is persisted so that
    malformed LLM output is rejected at the boundary.
    """

    is_relevant: bool
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
    address: str | None = None
    city: str | None = None
    state: str | None = None
    promotion_text: str | None = None
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    claims: list[LLMClaim] = []


class ManualIngestResponse(BaseModel):
    """Response body for POST /api/ingest/manual-url."""

    model_config = ConfigDict(from_attributes=True)

    source_id: uuid.UUID
    duplicate: bool
    relevant: bool
    event_id: uuid.UUID | None = None
    business_name: str | None = None
    event_type: str | None = None
    category: str | None = None
    event_date: datetime | None = None
    city: str | None = None
    state: str | None = None
    status: str | None = None
    confidence_score: float | None = None
    claims_count: int = 0
    fetch_status: str
    message: str = ""


# ---------------------------------------------------------------------------
# Worker candidate submission schemas
# ---------------------------------------------------------------------------


class CandidateClaimCreate(BaseModel):
    """A single claim extracted by the worker LangGraph pipeline."""

    claim_type: str
    claim_value: str
    claim_text: str | None = None
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


class CandidateEventCreate(BaseModel):
    """Payload the worker sends to create a candidate event from a source doc.

    Includes all extracted event fields, extracted claims, and the LLM call
    records for every OpenAI API call made while processing this source doc.
    """

    source_document_id: uuid.UUID
    search_run_id: uuid.UUID | None = None
    business_name: str | None = None
    event_name: str | None = None
    event_type: str = "unknown"
    category: str | None = None
    event_date_str: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    promotion_text: str | None = None
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    claims: list[CandidateClaimCreate] = []
    llm_calls: list[LLMCallCreate] = []


class CandidateEventResult(BaseModel):
    """Response for POST /api/ingest/source-document/{id}/candidate."""

    event_id: uuid.UUID | None = None
    created: bool = False
    irrelevant: bool = False
    duplicate: bool = False
    llm_call_ids: list[uuid.UUID] = []
    message: str = ""
