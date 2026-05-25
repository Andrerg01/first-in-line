"""Pydantic schemas for the admin deduplication and merge endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConflictSide(BaseModel):
    """One side of a side-by-side claim comparison."""

    id: uuid.UUID
    business_name: str | None = None
    claims: dict[str, list[str]] = Field(default_factory=dict)


class ConflictsResponse(BaseModel):
    """Response for GET /api/admin/events/{id}/conflicts."""

    event_a: ConflictSide
    event_b: ConflictSide
    conflicting_claim_types: list[str]


class SimilarityScore(BaseModel):
    """Similarity breakdown for a candidate pair."""

    event_id: uuid.UUID
    score: float
    name_score: float
    address_score: float
    date_score: float


class MergeCanonicalFields(BaseModel):
    """Validated canonical field overrides for merge operations."""

    business_name: str | None = None
    event_name: str | None = None
    event_date: datetime | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    category: str | None = None
    event_type: str | None = None
    promotion_text: str | None = None
    notes: str | None = None


class MergeRequest(BaseModel):
    """Request body for POST /api/admin/events/{id}/merge.

    The source event ID is taken from the path parameter.
    ``target_id`` is the canonical event to merge into.
    ``canonical_fields`` optionally overrides fields on the target event.
    """

    target_id: uuid.UUID
    canonical_fields: MergeCanonicalFields = Field(default_factory=MergeCanonicalFields)


class MergeResponse(BaseModel):
    """Response for POST /api/admin/events/{id}/merge."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_name: str | None
    status: str
    updated_at: datetime
    message: str = "Merge completed."


class DuplicateFlagRequest(BaseModel):
    """Request body for POST /api/admin/events/{id}/flag-duplicate."""

    duplicate_of_id: uuid.UUID | None = Field(
        default=None,
        description="The canonical event ID this event is a duplicate of. "
        "Pass null to clear the flag.",
    )


class DuplicateFlagResponse(BaseModel):
    """Response for POST /api/admin/events/{id}/flag-duplicate."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    possible_duplicate: bool
    duplicate_of_id: uuid.UUID | None
    message: str


class RetroactiveDedupResponse(BaseModel):
    """Response for POST /api/admin/dedup/retroactive-run."""

    scanned: int
    flagged: int
    cleared: int
    message: str


class GeocodeRunResponse(BaseModel):
    """Response for POST /api/admin/geocode/run."""

    attempted: int
    geocoded: int
    skipped: int
