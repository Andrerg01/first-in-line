"""Pydantic schemas for event claim API responses."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EventClaimResponse(BaseModel):
    """A single extracted claim associated with an event."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: uuid.UUID | None
    source_document_id: uuid.UUID
    claim_type: str
    claim_value: str | None
    claim_text: str | None
    confidence_score: float | None
    created_at: datetime
