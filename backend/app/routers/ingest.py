"""Ingest router — HTTP handler for the /api/ingest endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.ingest import ManualIngestRequest, ManualIngestResponse
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
