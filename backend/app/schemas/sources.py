"""Pydantic schemas for source document API responses."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SourceDocumentSummary(BaseModel):
    """Source document summary returned within event source responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    canonical_url: str | None
    domain: str | None
    title: str | None
    fetched_at: datetime | None
    fetch_status: str | None
    http_status: int | None


class EventSourceResponse(BaseModel):
    """Event-source join record with embedded source document summary."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: uuid.UUID
    source_document_id: uuid.UUID
    relationship_type: str
    created_at: datetime
    source_document: SourceDocumentSummary
