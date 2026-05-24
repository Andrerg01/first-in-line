"""Backend API client — HTTP wrapper for worker → backend API calls."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass

import httpx

from worker.app.config import settings

log = logging.getLogger(__name__)

_RETRYABLE_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})
_RETRYABLE_ERRORS = (
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.RemoteProtocolError,
    httpx.ReadError,
)


@dataclass
class SearchRunRecord:
    """Minimal fields from a SearchRun API response."""

    id: uuid.UUID
    status: str


@dataclass
class SourceDocumentResult:
    """Result from the store-source-document endpoint."""

    created: bool
    source_document_id: uuid.UUID
    duplicate: bool


def _api_request(
    method: str,
    path: str,
    payload: dict | None = None,
    *,
    label: str,
) -> dict:
    """Make an HTTP request to the backend API with retry on transient errors.

    Retries on 5xx responses and transport errors.  Skips retry for 4xx.

    Args:
        method: HTTP method string ('GET', 'POST', 'PATCH').
        path: URL path relative to the backend API base URL.
        payload: Optional JSON body.
        label: Short description for log messages.

    Returns:
        Parsed JSON response dict.

    Raises:
        RuntimeError: If all retries are exhausted.
        httpx.HTTPStatusError: For unretried 4xx errors.
    """
    url = f"{settings.backend_api_url}{path}"
    _max = settings.max_retries
    _base = settings.backoff_base
    last_exc: Exception | None = None

    for attempt in range(_max):
        try:
            with httpx.Client(timeout=settings.request_timeout) as client:
                resp = client.request(method, url, json=payload)

            # Don't retry deterministic client errors.
            if 400 <= resp.status_code < 500:
                resp.raise_for_status()

            if resp.status_code in _RETRYABLE_STATUSES and attempt < _max - 1:
                wait = _base * (2 ** attempt)
                log.warning(
                    "Backend API %s got HTTP %d, retrying in %.1fs (attempt %d/%d)",
                    label, resp.status_code, wait, attempt + 1, _max,
                )
                time.sleep(wait)
                continue

            resp.raise_for_status()
            return resp.json()

        except _RETRYABLE_ERRORS as exc:
            last_exc = exc
            if attempt < _max - 1:
                wait = _base * (2 ** attempt)
                log.warning(
                    "Backend API %s transport error, retrying (attempt %d/%d): %s",
                    label, attempt + 1, _max, exc,
                )
                time.sleep(wait)
            else:
                log.error("Backend API %s failed after %d attempts: %s", label, _max, exc)

    raise RuntimeError(
        f"Backend API {label} failed after {_max} attempts"
    ) from last_exc


def create_search_run(
    run_type: str = "scheduled_daily",
    query_set_version: str | None = None,
    notes: str | None = None,
) -> SearchRunRecord:
    """Start a new search run via the backend API.

    Args:
        run_type: Run type string persisted to the DB.
        query_set_version: Query template version label.
        notes: Optional notes.

    Returns:
        A ``SearchRunRecord`` with the new run's ID.
    """
    data = _api_request(
        "POST",
        "/api/ingest/search-run",
        {"run_type": run_type, "query_set_version": query_set_version, "notes": notes},
        label="create_search_run",
    )
    return SearchRunRecord(id=uuid.UUID(data["id"]), status=data["status"])


def finish_search_run(
    run_id: uuid.UUID,
    *,
    status: str,
    notes: str | None = None,
) -> None:
    """Mark a search run as completed or failed.

    Args:
        run_id: UUID of the SearchRun to close.
        status: Terminal status string (completed | failed | partial).
        notes: Optional notes to store on the run.
    """
    _api_request(
        "PATCH",
        f"/api/ingest/search-run/{run_id}",
        {"status": status, "notes": notes},
        label="finish_search_run",
    )


def save_search_results(
    run_id: uuid.UUID,
    results: list[dict],
) -> int:
    """Bulk-insert search results for a run.

    Args:
        run_id: UUID of the parent SearchRun.
        results: List of result dicts (query, rank, title, url, snippet, search_provider).

    Returns:
        Number of rows saved.
    """
    data = _api_request(
        "POST",
        f"/api/ingest/search-run/{run_id}/results",
        {"results": results},
        label="save_search_results",
    )
    return int(data.get("saved", 0))


def store_source_document(
    *,
    url: str,
    canonical_url: str | None,
    domain: str | None,
    title: str | None,
    visible_text: str,
    visible_text_hash: str,
    http_status: int | None,
    content_type: str | None,
    fetch_status: str,
    error_message: str | None,
    search_run_id: uuid.UUID | None = None,
) -> SourceDocumentResult:
    """Persist a source document, skipping duplicates by text hash.

    Args:
        url: Original URL that was fetched.
        canonical_url: Canonicalized URL after redirects.
        domain: Extracted domain.
        title: Page title.
        visible_text: Normalised visible text.
        visible_text_hash: SHA-256 of the normalised text.
        http_status: HTTP response status code.
        content_type: Response Content-Type header.
        fetch_status: 'success' or 'failed'.
        error_message: Error description if fetch failed.
        search_run_id: Optional FK to the parent SearchRun.

    Returns:
        A ``SourceDocumentResult`` indicating whether the record was created.
    """
    payload: dict = {
        "url": url,
        "canonical_url": canonical_url,
        "domain": domain,
        "title": title,
        "visible_text": visible_text,
        "visible_text_hash": visible_text_hash,
        "http_status": http_status,
        "content_type": content_type,
        "fetch_status": fetch_status,
        "error_message": error_message,
    }
    if search_run_id is not None:
        payload["search_run_id"] = str(search_run_id)

    data = _api_request(
        "POST",
        "/api/ingest/source-document",
        payload,
        label="store_source_document",
    )
    return SourceDocumentResult(
        created=data["created"],
        source_document_id=uuid.UUID(data["source_document_id"]),
        duplicate=data["duplicate"],
    )
