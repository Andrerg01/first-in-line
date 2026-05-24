"""Ingest service — orchestrates the manual URL ingestion pipeline and
scheduled search run persistence.

Functions:
- ingest_manual_url: 8-step manual ingestion pipeline (fetch → extract → save).
- start_search_run: Create a SearchRun record for a worker discovery run.
- finish_search_run: Mark a SearchRun as completed/failed.
- save_search_results: Bulk-insert SearchResult rows for a run.
- store_source_document_from_fetch: Dedup + persist a SourceDocument from MCP output.
- save_candidate_event: Persist a candidate event + claims + LLM calls from the worker.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone

import httpx
from openai import OpenAI
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import ConfigurationError, ExtractionError, MCPError
from app.models.events import Event
from app.models.sources import SourceDocument
from app.repositories import (
    claims_repository,
    event_repository,
    llm_call_repository,
    processing_repository,
    search_repository,
    source_repository,
    telemetry_repository,
)
from app.schemas.ingest import (
    CandidateEventCreate,
    CandidateEventResult,
    LLMExtractionResult,
    ManualIngestResponse,
)
from app.schemas.search import (
    SearchResultCreate,
    SearchRunCreate,
    SearchRunOut,
    SearchRunStatusUpdate,
    SourceDocumentFromFetch,
    SourceDocumentStoreResult,
)
from app.schemas.telemetry import ToolCallCreate

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry configuration
# ---------------------------------------------------------------------------

_MAX_RETRIES = 3  # total attempts (1 initial + 2 retries)
_BACKOFF_BASE = 1.0  # seconds; wait = _BACKOFF_BASE * 2**attempt

_RETRYABLE_TRANSPORT_ERRORS = (
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.RemoteProtocolError,
    httpx.ReadError,
)


def _http_call_with_retry(
    fn: "Callable[[], httpx.Response]",
    *,
    label: str,
    max_retries: int = _MAX_RETRIES,
) -> httpx.Response:
    """Execute fn() up to max_retries times with exponential backoff.

    Retries on transport errors (connection, timeout, protocol) and HTTP 5xx
    responses. Does not retry HTTP 4xx (client errors).

    Args:
        fn: Zero-argument callable that performs the HTTP call and returns
            an ``httpx.Response``.
        label: Short string used in log messages to identify the call.
        max_retries: Total number of attempts.

    Returns:
        The first successful ``httpx.Response`` (after ``raise_for_status``).

    Raises:
        The last captured exception when all attempts are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = fn()
            resp.raise_for_status()
            return resp
        except _RETRYABLE_TRANSPORT_ERRORS as exc:
            last_exc = exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500:
                raise  # 4xx — deterministic failure, do not retry
            last_exc = exc
        if attempt < max_retries - 1:
            wait = _BACKOFF_BASE * (2 ** attempt)
            log.warning(
                "%s failed (attempt %d/%d), retrying in %.1fs: %s",
                label, attempt + 1, max_retries, wait, last_exc,
            )
            time.sleep(wait)
        else:
            log.error("%s failed after %d attempts: %s", label, max_retries, last_exc)
    raise last_exc  # type: ignore[misc]

# ---------------------------------------------------------------------------
# System prompt for OpenAI extraction
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert at identifying and extracting structured information about \
restaurant, cafe, brewery, food truck, and retail grand opening events from \
web page text.

Given the visible text of a web page, determine whether it describes a grand \
opening (or similar: soft opening, ribbon cutting, reopening, anniversary \
opening) event and extract structured data.

Respond with a valid JSON object matching this schema exactly:
{
  "is_relevant": true or false,
  "business_name": "string or null",
  "event_name": "string or null",
  "event_type": "grand_opening | soft_opening | ribbon_cutting | reopening | anniversary | unknown",
  "category": "restaurant | cafe | food_truck | brewery | retail | other | null",
  "event_date_str": "YYYY-MM-DD or null",
  "address": "string or null",
  "city": "string or null",
  "state": "2-letter US state code or null",
  "promotion_text": "string or null",
  "confidence_score": 0.0 to 1.0,
  "claims": [
    {
      "claim_type": "business_name | event_date | address | city | state | \
promotion | event_type | category | opening_status",
      "claim_value": "the extracted value",
      "claim_text": "the exact quote or sentence from the page text"
    }
  ]
}

Set is_relevant to true only if the page clearly describes an upcoming or \
recent grand opening (or similar) event for a restaurant, cafe, food truck, \
brewery, or retail business.
"""


# ---------------------------------------------------------------------------
# MCP HTTP helpers — kept as module-level functions so tests can patch them
# ---------------------------------------------------------------------------


def _call_mcp_fetch_page(url: str) -> dict:
    """Call the MCP web.fetch_page tool endpoint with automatic retry.

    Retries up to ``_MAX_RETRIES`` times on transient transport errors or HTTP
    5xx responses from the MCP server, using exponential backoff.

    Args:
        url: URL to fetch.

    Returns:
        Parsed JSON response from the MCP server.

    Raises:
        MCPError: If all retry attempts fail.
    """
    endpoint = f"{settings.mcp_server_url}/tools/web.fetch_page"
    try:
        resp = _http_call_with_retry(
            lambda: httpx.post(endpoint, json={"url": url}, timeout=30.0),
            label="MCP fetch_page",
        )
        return resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.error("MCP fetch_page failed for %s: %s", url, exc)
        raise MCPError("Page fetch service is unavailable.") from exc


def _call_mcp_normalize_text(text: str) -> dict:
    """Call the MCP web.normalize_text tool endpoint with automatic retry.

    Retries up to ``_MAX_RETRIES`` times on transient transport errors or HTTP
    5xx responses from the MCP server, using exponential backoff.

    Args:
        text: Raw visible text to normalise.

    Returns:
        Parsed JSON with ``normalized_text`` and ``text_hash`` keys.

    Raises:
        MCPError: If all retry attempts fail.
    """
    endpoint = f"{settings.mcp_server_url}/tools/web.normalize_text"
    try:
        resp = _http_call_with_retry(
            lambda: httpx.post(endpoint, json={"text": text}, timeout=10.0),
            label="MCP normalize_text",
        )
        return resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.error("MCP normalize_text failed: %s", exc)
        raise MCPError("Text processing service is unavailable.") from exc


# ---------------------------------------------------------------------------
# OpenAI extraction helper
# ---------------------------------------------------------------------------


def _extract_event_data(url: str, normalized_text: str) -> LLMExtractionResult:
    """Call OpenAI to extract structured event data from page text.

    Args:
        url: Source URL used only for log context.
        normalized_text: Cleaned visible page text (truncated to 8 000 chars).

    Returns:
        A validated ``LLMExtractionResult``.

    Raises:
        ConfigurationError: If the OpenAI API key is not configured.
        ExtractionError: If the OpenAI call fails or the response fails Pydantic validation.
    """
    if not settings.openai_api_key:
        raise ConfigurationError("OPENAI_API_KEY is not configured on the server.")

    # max_retries=3 instructs the OpenAI SDK to retry on rate limits and
    # transient server errors with its own exponential backoff.
    client = OpenAI(api_key=settings.openai_api_key, max_retries=3)
    user_content = (
        f"URL: {url}\n\nPage text (truncated to 8000 chars):\n"
        + normalized_text[:8000]
    )

    try:
        completion = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
    except Exception as exc:
        log.error("OpenAI extraction failed for %s: %s", url, exc)
        raise ExtractionError("Event extraction service is unavailable.") from exc

    raw_json = completion.choices[0].message.content or "{}"
    try:
        data = json.loads(raw_json)
        return LLMExtractionResult.model_validate(data)
    except Exception as exc:
        log.error(
            "OpenAI output validation failed for %s: %s\nRaw: %s", url, exc, raw_json
        )
        raise ExtractionError("Extraction output was invalid.") from exc


# ---------------------------------------------------------------------------
# Date parsing helper
# ---------------------------------------------------------------------------


def _parse_event_date(date_str: str | None) -> datetime | None:
    """Parse a YYYY-MM-DD string into a UTC-aware datetime, or return None.

    Args:
        date_str: Date string from LLM output.

    Returns:
        A timezone-aware datetime or None if parsing fails.
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def ingest_manual_url(db: Session, url: str) -> ManualIngestResponse:
    """Execute the full manual URL ingestion pipeline.

    Fetches the page via MCP, normalises the text, deduplicates by hash,
    calls OpenAI for extraction, then persists the source document, event,
    claims, and a processing decision.

    Args:
        db: Active database session.
        url: URL submitted for ingestion.

    Returns:
        A ``ManualIngestResponse`` describing the outcome.

    Raises:
        MCPError: If the MCP fetch or normalize call fails.
        ConfigurationError: If the OpenAI API key is missing.
        ExtractionError: If the OpenAI call fails or returns invalid output.
    """
    # 1. Fetch page via MCP -----------------------------------------------
    fetch_result = _call_mcp_fetch_page(url)

    # Guard: early-exit if fetch failed or yielded no visible text.
    # Using hash("") for dedup would collide across all failed fetches.
    fetch_status = fetch_result.get("fetch_status", "failed")
    visible_text: str = fetch_result.get("visible_text") or ""
    if fetch_status != "success" or not visible_text.strip():
        source_doc = source_repository.create_source_document(
            db,
            url=url,
            canonical_url=fetch_result.get("canonical_url") or url,
            domain=fetch_result.get("domain"),
            title=fetch_result.get("title"),
            visible_text=visible_text or None,
            visible_text_hash=None,
            fetch_status=fetch_status,
            http_status=fetch_result.get("http_status"),
            content_type=fetch_result.get("content_type"),
            fetch_method="manual",
            fetched_at=datetime.now(timezone.utc),
            error_message=fetch_result.get("error_message"),
        )
        processing_repository.create_processing_decision(
            db,
            source_document_id=source_doc.id,
            event_id=None,
            decision_type="manual_ingest",
            decision_value="fetch_failed",
            reason=(
                f"fetch_status={fetch_status}; "
                f"error={fetch_result.get('error_message')}"
            ),
            model_name=None,
        )
        db.commit()
        error_msg = fetch_result.get("error_message") or "empty content"
        return ManualIngestResponse(
            source_id=source_doc.id,
            duplicate=False,
            relevant=False,
            fetch_status=fetch_status,
            message=f"Page fetch failed: {error_msg}",
        )

    # 2. Normalise text via MCP -------------------------------------------
    norm_result = _call_mcp_normalize_text(visible_text)
    text_hash: str | None = norm_result.get("text_hash")
    normalized_text: str | None = norm_result.get("normalized_text")
    if not text_hash or normalized_text is None:
        log.error("MCP normalize_text returned unexpected payload: %s", norm_result)
        raise MCPError("Text processing service returned an unexpected response.")

    # 3. Deduplication check ----------------------------------------------
    existing_doc = source_repository.find_source_by_hash(db, text_hash)  # type: ignore[arg-type]
    if existing_doc:
        event_row = source_repository.get_event_source_for_source_document(
            db, existing_doc.id
        )
        event: Event | None = (
            event_repository.get_event_by_id(db, event_row.event_id)
            if event_row
            else None
        )
        return ManualIngestResponse(
            source_id=existing_doc.id,
            duplicate=True,
            relevant=event is not None,
            event_id=event.id if event else None,
            business_name=event.business_name if event else None,
            event_type=event.event_type if event else None,
            category=event.category if event else None,
            event_date=event.event_date if event else None,
            city=event.city if event else None,
            state=event.state if event else None,
            status=event.status if event else None,
            confidence_score=(
                float(event.confidence_score)
                if event and event.confidence_score is not None
                else None
            ),
            claims_count=0,
            fetch_status="skipped",
            message="Duplicate URL — source document already exists.",
        )

    # 4. Persist source document — committed before any LLM call so the
    #    source document always survives even if extraction fails.
    source_doc = source_repository.create_source_document(
        db,
        url=url,
        canonical_url=fetch_result.get("canonical_url") or url,
        domain=fetch_result.get("domain"),
        title=fetch_result.get("title"),
        visible_text=visible_text,
        visible_text_hash=text_hash,
        fetch_status=fetch_result.get("fetch_status", "success"),
        http_status=fetch_result.get("http_status"),
        content_type=fetch_result.get("content_type"),
        fetch_method="manual",
        fetched_at=datetime.now(timezone.utc),
        error_message=fetch_result.get("error_message"),
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Duplicate arrived via concurrent request — treat as dedup hit.
        db.expire_all()
        existing_doc = source_repository.find_source_by_hash(db, text_hash)  # type: ignore[arg-type]
        if existing_doc:
            event_row = source_repository.get_event_source_for_source_document(
                db, existing_doc.id
            )
            event: Event | None = (
                event_repository.get_event_by_id(db, event_row.event_id)
                if event_row
                else None
            )
            return ManualIngestResponse(
                source_id=existing_doc.id,
                duplicate=True,
                relevant=event is not None,
                event_id=event.id if event else None,
                business_name=event.business_name if event else None,
                event_type=event.event_type if event else None,
                category=event.category if event else None,
                event_date=event.event_date if event else None,
                city=event.city if event else None,
                state=event.state if event else None,
                status=event.status if event else None,
                confidence_score=(
                    float(event.confidence_score)
                    if event and event.confidence_score is not None
                    else None
                ),
                claims_count=0,
                fetch_status="skipped",
                message="Duplicate URL — source document already exists.",
            )
        raise

    # 5. OpenAI extraction ------------------------------------------------
    extraction = _extract_event_data(url, normalized_text)

    # 6. Create event (if relevant) and event-source link -----------------
    event: Event | None = None
    if extraction.is_relevant:
        event = event_repository.create_event(
            db,
            business_name=extraction.business_name,
            event_name=extraction.event_name,
            event_type=extraction.event_type or "unknown",
            category=extraction.category,
            event_date=_parse_event_date(extraction.event_date_str),
            address=extraction.address,
            city=extraction.city,
            state=extraction.state,
            promotion_text=extraction.promotion_text,
            status="candidate",
            confidence_score=extraction.confidence_score,
        )
        source_repository.create_event_source(
            db, event_id=event.id, source_document_id=source_doc.id
        )

    # 7. Persist claims ---------------------------------------------------
    claims_count = 0
    for claim in extraction.claims:
        claims_repository.create_claim(
            db,
            event_id=event.id if event else None,
            source_document_id=source_doc.id,
            claim_type=claim.claim_type,
            claim_value=claim.claim_value,
            claim_text=claim.claim_text,
            confidence_score=extraction.confidence_score,
        )
        claims_count += 1

    # 8. Record processing decision ---------------------------------------
    processing_repository.create_processing_decision(
        db,
        source_document_id=source_doc.id,
        event_id=event.id if event else None,
        decision_type="manual_ingest",
        decision_value="candidate_created" if event else "not_relevant",
        reason=(
            f"is_relevant={extraction.is_relevant}; "
            f"confidence={extraction.confidence_score}"
        ),
        model_name=settings.openai_model,
    )

    db.commit()  # commits event, claims, event_source, processing_decision

    return ManualIngestResponse(
        source_id=source_doc.id,
        duplicate=False,
        relevant=extraction.is_relevant,
        event_id=event.id if event else None,
        business_name=event.business_name if event else None,
        event_type=event.event_type if event else None,
        category=event.category if event else None,
        event_date=event.event_date if event else None,
        city=event.city if event else None,
        state=event.state if event else None,
        status=event.status if event else None,
        confidence_score=(
            float(event.confidence_score)
            if event and event.confidence_score is not None
            else None
        ),
        claims_count=claims_count,
        fetch_status=fetch_result.get("fetch_status", "success"),
        message=(
            "Candidate event created."
            if event
            else "Page is not relevant to grand openings."
        ),
    )


# ---------------------------------------------------------------------------
# Search run and source document persistence (called by the worker)
# ---------------------------------------------------------------------------


def start_search_run(db: Session, body: SearchRunCreate) -> SearchRunOut:
    """Create and persist a new SearchRun with status=running.

    Args:
        db: Active database session.
        body: Parameters for the new run.

    Returns:
        A ``SearchRunOut`` representing the newly created run.
    """
    run = search_repository.create_search_run(
        db,
        run_type=body.run_type,
        query_set_version=body.query_set_version,
        notes=body.notes,
    )
    return SearchRunOut.model_validate(run)


def finish_search_run(
    db: Session, run_id: uuid.UUID, body: SearchRunStatusUpdate
) -> SearchRunOut | None:
    """Mark a SearchRun as completed or failed and persist aggregate stats.

    Args:
        db: Active database session.
        run_id: UUID of the SearchRun to close.
        body: Terminal status, optional notes, and optional aggregate stats.

    Returns:
        Updated ``SearchRunOut``, or ``None`` if the run was not found.
    """
    run = search_repository.update_search_run_status(
        db,
        run_id,
        status=body.status,
        notes=body.notes,
        queries_executed=body.queries_executed,
        search_results_found=body.search_results_found,
        urls_attempted=body.urls_attempted,
        source_docs_created=body.source_docs_created,
        source_docs_skipped=body.source_docs_skipped,
        fetch_errors=body.fetch_errors,
        elapsed_seconds=body.elapsed_seconds,
    )
    if run is None:
        return None
    return SearchRunOut.model_validate(run)


def save_tool_calls(
    db: Session,
    run_id: uuid.UUID,
    tool_calls: list[ToolCallCreate],
) -> int | None:
    """Bulk-insert pipeline tool call telemetry for a search run.

    Args:
        db: Active database session.
        run_id: UUID of the parent SearchRun.
        tool_calls: List of ``ToolCallCreate`` schema instances.

    Returns:
        Number of rows inserted, or ``None`` if the SearchRun was not found.
    """
    run = search_repository.get_search_run(db, run_id)
    if run is None:
        log.warning("save_tool_calls: SearchRun %s not found, dropping records", run_id)
        return None
    records = [tc.model_dump() for tc in tool_calls]
    count = telemetry_repository.bulk_insert_tool_calls(db, run_id, records)
    db.commit()
    log.info("Saved %d tool call records for run %s", count, run_id)
    return count


def save_search_results(
    db: Session,
    run_id: uuid.UUID,
    results: list[SearchResultCreate],
) -> int | None:
    """Bulk-insert SearchResult rows for a run.

    Verifies the parent SearchRun exists before inserting.

    Args:
        db: Active database session.
        run_id: UUID of the parent SearchRun.
        results: List of result payloads to persist.

    Returns:
        Number of rows saved, or ``None`` if the SearchRun was not found.
    """
    run = search_repository.get_search_run(db, run_id)
    if run is None:
        return None
    for item in results:
        search_repository.create_search_result(
            db,
            search_run_id=run_id,
            query=item.query,
            rank=item.rank,
            title=item.title,
            url=item.url,
            snippet=item.snippet,
            search_provider=item.search_provider,
        )
    return len(results)


def store_source_document_from_fetch(
    db: Session, body: SourceDocumentFromFetch
) -> SourceDocumentStoreResult:
    """Persist a source document from a worker fetch result, skipping duplicates.

    Checks for an existing SourceDocument with the same ``visible_text_hash``.
    If found, returns the existing record's ID with ``created=False``.
    Otherwise inserts a new record.

    Args:
        db: Active database session.
        body: Fetch result payload including hash, text, and metadata.

    Returns:
        A ``SourceDocumentStoreResult`` with the document ID and creation flag.
    """
    existing = source_repository.find_source_by_hash(db, body.visible_text_hash)
    if existing is not None:
        log.info(
            "Source document duplicate skipped: hash=%s url=%s",
            body.visible_text_hash,
            body.url,
        )
        return SourceDocumentStoreResult(
            created=False,
            source_document_id=existing.id,
            duplicate=True,
        )

    now = datetime.now(timezone.utc)
    doc = SourceDocument(
        url=body.url,
        canonical_url=body.canonical_url,
        domain=body.domain,
        title=body.title,
        fetched_at=now,
        visible_text=body.visible_text,
        visible_text_hash=body.visible_text_hash,
        fetch_status=body.fetch_status,
        http_status=body.http_status,
        content_type=body.content_type,
        error_message=body.error_message,
        fetch_method="scheduled_worker",
    )
    db.add(doc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Race condition: another process inserted the same hash concurrently.
        existing = source_repository.find_source_by_hash(db, body.visible_text_hash)
        if existing:
            return SourceDocumentStoreResult(
                created=False,
                source_document_id=existing.id,
                duplicate=True,
            )
        raise
    db.refresh(doc)
    log.info("New source document stored: id=%s url=%s", doc.id, body.url)
    return SourceDocumentStoreResult(
        created=True,
        source_document_id=doc.id,
        duplicate=False,
    )


# ---------------------------------------------------------------------------
# Worker candidate event persistence
# ---------------------------------------------------------------------------


def save_candidate_event(
    db: Session, body: CandidateEventCreate
) -> CandidateEventResult:
    """Persist a candidate event, its claims, and all LLM call records.

    Called by the worker after the LangGraph extraction pipeline produces
    an extraction result for a source document.  Idempotent: if the source
    document already has a linked event the call returns with
    ``duplicate=True`` and no new records are written.

    Atomic: all inserts (LLM calls, event, event_source, claims, processing
    decision) are committed together.  If any step fails the transaction is
    rolled back so the database stays consistent.

    Args:
        db: Active database session.
        body: Validated ``CandidateEventCreate`` payload from the worker.

    Returns:
        A ``CandidateEventResult`` describing the outcome.
    """
    # ------------------------------------------------------------------
    # 1. Guard — skip if source document already linked to an event
    # ------------------------------------------------------------------
    event_source_row = source_repository.get_event_source_for_source_document(
        db, body.source_document_id
    )
    if event_source_row is not None:
        log.info(
            "save_candidate_event: source_doc %s already linked to event %s — skipping",
            body.source_document_id,
            event_source_row.event_id,
        )
        return CandidateEventResult(
            event_id=event_source_row.event_id,
            duplicate=True,
            message="Source document already linked to an event.",
        )

    # ------------------------------------------------------------------
    # 2. Log all LLM calls (flush; do not commit yet)
    # ------------------------------------------------------------------
    llm_call_records = llm_call_repository.bulk_create_llm_calls(
        db, body.llm_calls
    )
    llm_call_ids = [r.id for r in llm_call_records]

    # ------------------------------------------------------------------
    # 3. Handle irrelevant pages — record decision and return early
    # ------------------------------------------------------------------
    # A candidate with no business_name and no claims means the LangGraph
    # classified the page as irrelevant.  Persist a processing decision and
    # return without creating an event.
    if not body.business_name and not body.claims:
        processing_repository.create_processing_decision(
            db,
            source_document_id=body.source_document_id,
            event_id=None,
            decision_type="worker_extraction",
            decision_value="irrelevant",
            reason="LangGraph classified page as not relevant to a grand-opening event.",
            model_name=None,
            llm_call_id=llm_call_ids[0] if llm_call_ids else None,
        )
        db.commit()
        return CandidateEventResult(
            irrelevant=True,
            llm_call_ids=llm_call_ids,
            message="Page classified as irrelevant; no event created.",
        )

    # ------------------------------------------------------------------
    # 4. Create event record
    # ------------------------------------------------------------------
    event_date = _parse_event_date(body.event_date_str)
    event = event_repository.create_event(
        db,
        business_name=body.business_name,
        event_name=body.event_name,
        event_type=body.event_type or "unknown",
        category=body.category,
        event_date=event_date,
        address=body.address,
        city=body.city,
        state=body.state,
        promotion_text=body.promotion_text,
        status="candidate",
        confidence_score=body.confidence_score,
    )

    # ------------------------------------------------------------------
    # 5. Link source document → event
    # ------------------------------------------------------------------
    source_repository.create_event_source(
        db, event_id=event.id, source_document_id=body.source_document_id
    )

    # ------------------------------------------------------------------
    # 6. Persist claims
    # ------------------------------------------------------------------
    for claim in body.claims:
        claims_repository.create_claim(
            db,
            event_id=event.id,
            source_document_id=body.source_document_id,
            claim_type=claim.claim_type,
            claim_value=claim.claim_value,
            claim_text=claim.claim_text,
            confidence_score=claim.confidence_score,
        )

    # ------------------------------------------------------------------
    # 7. Persist processing decision (link to extraction LLM call)
    # ------------------------------------------------------------------
    # The last llm_call in the list is the extraction call (the one that
    # produced the event data).  Earlier calls are classification calls.
    extraction_call_id = llm_call_ids[-1] if llm_call_ids else None
    processing_repository.create_processing_decision(
        db,
        source_document_id=body.source_document_id,
        event_id=event.id,
        decision_type="worker_extraction",
        decision_value="candidate_created",
        reason=f"LangGraph extracted candidate event; confidence={body.confidence_score:.2f}",
        model_name=None,
        llm_call_id=extraction_call_id,
    )

    db.commit()
    log.info(
        "save_candidate_event: created event %s for source_doc %s",
        event.id,
        body.source_document_id,
    )
    return CandidateEventResult(
        event_id=event.id,
        created=True,
        llm_call_ids=llm_call_ids,
        message=f"Candidate event created: {body.business_name!r}",
    )

