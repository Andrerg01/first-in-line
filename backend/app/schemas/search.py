"""Pydantic schemas for search run and search result API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SearchRunCreate(BaseModel):
    """Payload to start a new search run."""

    run_type: str = "scheduled_daily"
    query_set_version: str | None = None
    notes: str | None = None


class SearchRunOut(BaseModel):
    """Search run response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_type: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    query_set_version: str | None
    notes: str | None
    created_at: datetime


class SearchRunStatusUpdate(BaseModel):
    """Payload to update a search run's terminal status."""

    status: str  # completed | failed | partial | cancelled
    notes: str | None = None


class SearchResultCreate(BaseModel):
    """A single search result to persist for a run."""

    query: str | None = None
    rank: int | None = None
    title: str | None = None
    url: str
    snippet: str | None = None
    search_provider: str | None = None


class SearchResultsCreate(BaseModel):
    """Bulk search result payload for a run."""

    results: list[SearchResultCreate]


class SearchResultOut(BaseModel):
    """Search result response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    search_run_id: uuid.UUID
    query: str | None
    rank: int | None
    title: str | None
    url: str
    snippet: str | None
    search_provider: str | None
    created_at: datetime


class SourceDocumentFromFetch(BaseModel):
    """Payload to store a source document produced by MCP web.fetch_page + web.normalize_text."""

    url: str
    canonical_url: str | None = None
    domain: str | None = None
    title: str | None = None
    visible_text: str
    visible_text_hash: str
    http_status: int | None = None
    content_type: str | None = None
    fetch_status: str = "success"
    error_message: str | None = None
    search_run_id: uuid.UUID | None = None


class SourceDocumentStoreResult(BaseModel):
    """Result of a store-or-skip source document operation."""

    created: bool
    source_document_id: uuid.UUID
    duplicate: bool
