"""Ingest router — HTTP handler for the /api/ingest endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.ingest import (
    CandidateEventCreate,
    CandidateEventResult,
    ManualIngestRequest,
    ManualIngestResponse,
)
from app.schemas.search import (
    SearchResultsCreate,
    SearchRunCreate,
    SearchRunOut,
    SearchRunStatusUpdate,
    SourceDocumentFromFetch,
    SourceDocumentStoreResult,
)
from app.schemas.telemetry import ToolCallsBulkCreate
from app.services import ingest_service

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("/manual-url", response_model=ManualIngestResponse)
def manual_ingest(
    body: ManualIngestRequest,
    db: Session = Depends(get_db),
) -> ManualIngestResponse:
    """Ingest a URL manually and extract a candidate grand-opening event.

    Fetches the page via the MCP server, normalises and hashes the text,
    deduplicates against existing source documents, calls OpenAI for
    structured extraction, then persists the source document, claims, and
    candidate event.

    Args:
        body: Request body containing the URL to ingest.
        db: Injected database session.

    Returns:
        A ManualIngestResponse describing the ingestion outcome.
    """
    return ingest_service.ingest_manual_url(db, body.url)


@router.post("/search-run", response_model=SearchRunOut, status_code=201)
def create_search_run(
    body: SearchRunCreate,
    db: Session = Depends(get_db),
) -> SearchRunOut:
    """Start a new search run and return its record.

    Called by the worker at the beginning of each discovery run.

    Args:
        body: Payload with run_type and optional metadata.
        db: Injected database session.

    Returns:
        The created ``SearchRunOut``.
    """
    return ingest_service.start_search_run(db, body)


@router.patch("/search-run/{run_id}", response_model=SearchRunOut)
def update_search_run(
    run_id: uuid.UUID,
    body: SearchRunStatusUpdate,
    db: Session = Depends(get_db),
) -> SearchRunOut:
    """Update the terminal status of a search run.

    Args:
        run_id: UUID of the SearchRun to update.
        body: New status and optional notes.
        db: Injected database session.

    Returns:
        The updated ``SearchRunOut``.

    Raises:
        HTTPException 404: If no SearchRun exists for the given ID.
    """
    result = ingest_service.finish_search_run(db, run_id, body)
    if result is None:
        raise HTTPException(status_code=404, detail="SearchRun not found")
    return result


@router.post("/search-run/{run_id}/results", status_code=201)
def add_search_results(
    run_id: uuid.UUID,
    body: SearchResultsCreate,
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Bulk-insert search results for a run.

    Args:
        run_id: UUID of the parent SearchRun.
        body: List of search result payloads.
        db: Injected database session.

    Returns:
        Dictionary with ``saved`` count.

    Raises:
        HTTPException 404: If no SearchRun exists for the given ID.
    """
    count = ingest_service.save_search_results(db, run_id, body.results)
    if count is None:
        raise HTTPException(status_code=404, detail="SearchRun not found")
    return {"saved": count}


@router.post("/source-document", response_model=SourceDocumentStoreResult, status_code=201)
def store_source_document(
    body: SourceDocumentFromFetch,
    db: Session = Depends(get_db),
) -> SourceDocumentStoreResult:
    """Store a fetched source document, skipping duplicates by text hash.

    The worker calls this after fetching and normalising a page. If a
    source document with the same ``visible_text_hash`` already exists the
    existing record's ID is returned with ``created=False`` and
    ``duplicate=True``.

    Args:
        body: Fetch result payload including the text hash for dedup.
        db: Injected database session.

    Returns:
        A ``SourceDocumentStoreResult`` indicating whether the record was
        newly created or was a duplicate.
    """
    return ingest_service.store_source_document_from_fetch(db, body)


@router.post("/search-run/{run_id}/tool-calls", status_code=201)
def add_tool_calls(
    run_id: uuid.UUID,
    body: ToolCallsBulkCreate,
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Bulk-insert pipeline tool call telemetry for a search run.

    The worker calls this once per run after all MCP and API calls are
    complete.  Records are stored in ``pipeline_tool_calls`` for diagnostics,
    rate-limit analysis, and latency trending.

    Args:
        run_id: UUID of the parent SearchRun.
        body: List of tool call records.
        db: Injected database session.

    Returns:
        Dictionary with ``saved`` count.

    Raises:
        HTTPException 404: If no SearchRun exists for the given ID.
    """
    count = ingest_service.save_tool_calls(db, run_id, body.tool_calls)
    if count is None:
        raise HTTPException(status_code=404, detail="SearchRun not found")
    return {"saved": count}


@router.post(
    "/source-document/{source_document_id}/candidate",
    response_model=CandidateEventResult,
    status_code=201,
)
def create_candidate_event(
    source_document_id: uuid.UUID,
    body: CandidateEventCreate,
    db: Session = Depends(get_db),
) -> CandidateEventResult:
    """Create a candidate event from a worker LangGraph extraction result.

    The worker calls this after the extraction graph produces a result for
    a source document.  Persists the event, claims, and all LLM call records
    in a single transaction.  Idempotent: if the source document already has
    a linked event the response contains ``duplicate=True``.

    Args:
        source_document_id: UUID of the source document that was processed.
        body: Extraction result payload including event fields and LLM calls.
        db: Injected database session.

    Returns:
        A ``CandidateEventResult`` describing whether an event was created.
    """
    return ingest_service.save_candidate_event(db, body, source_document_id=source_document_id)

