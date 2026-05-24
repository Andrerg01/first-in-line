"""Ingest service — orchestrates the manual URL ingestion pipeline.

Steps executed by ingest_manual_url:
1. Call MCP web.fetch_page to retrieve visible text from the URL.
2. Call MCP web.normalize_text to clean and SHA-256 hash the text.
3. Check for a duplicate source document by hash.
4. Persist the SourceDocument.
5. Call OpenAI to extract structured event data; validate with Pydantic.
6. Persist the Event (if relevant), EventSource link, EventClaims, and
   a ProcessingDecision for auditability.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import httpx
from openai import OpenAI
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import ConfigurationError, ExtractionError, MCPError
from app.models.events import Event
from app.repositories import (
    claims_repository,
    event_repository,
    processing_repository,
    source_repository,
)
from app.schemas.ingest import LLMExtractionResult, ManualIngestResponse

log = logging.getLogger(__name__)

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
    """Call the MCP web.fetch_page tool endpoint.

    Args:
        url: URL to fetch.

    Returns:
        Parsed JSON response from the MCP server.

    Raises:
        MCPError: If the HTTP request to the MCP server fails or returns an error.
    """
    endpoint = f"{settings.mcp_server_url}/tools/web.fetch_page"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(endpoint, json={"url": url})
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.error("MCP fetch_page failed for %s: %s", url, exc)
        raise MCPError("Page fetch service is unavailable.") from exc


def _call_mcp_normalize_text(text: str) -> dict:
    """Call the MCP web.normalize_text tool endpoint.

    Args:
        text: Raw visible text to normalise.

    Returns:
        Parsed JSON with ``normalized_text`` and ``text_hash`` keys.

    Raises:
        MCPError: If the HTTP request to the MCP server fails or returns an error.
    """
    endpoint = f"{settings.mcp_server_url}/tools/web.normalize_text"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(endpoint, json={"text": text})
        resp.raise_for_status()
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

    client = OpenAI(api_key=settings.openai_api_key)
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
