"""MCP client — thin HTTP wrapper for calling MCP server tools from the worker.

Rate-limit handling
-------------------
DuckDuckGo applies IP-level rate limits to container environments.  When the
search provider is rate-limited, DDGS hangs until the HTTP timeout fires
rather than returning an immediate error code.

Detection:
  If a ``web.search`` call fails with ``RuntimeError`` (all retries exhausted)
  and the underlying cause is ``httpx.TimeoutException``, the client emits a
  prominent WARNING recommending the operator wait 30–60 minutes:

    WARNING  Rate limit likely active for DuckDuckGo.
             All search retries timed out.  Wait 30–60 minutes before
             the next run, or set SEARCH_PROVIDER=stub for testing.

Mitigation (current defaults):
  - ``_SEARCH_TIMEOUT = 8 s`` — DDGS call timeout in the MCP server.
  - MCP client uses ``timeout=12 s`` + ``max_retries=1`` for search so each
    query fails in at most ~12 s instead of 3 × 30 s = 90 s.
  - ``SCRAPER_RATE_LIMIT_SECONDS = 2 s`` (default) adds a mandatory pause between
    consecutive queries so normal traffic doesn't trigger the limit.
"""

from __future__ import annotations

import logging
import time
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
class SearchResultItem:
    """A single result from web.search."""

    rank: int
    title: str | None
    url: str
    snippet: str | None


@dataclass
class SearchResponse:
    """Response from web.search."""

    query: str
    provider: str
    results: list[SearchResultItem]


@dataclass
class FetchPageResponse:
    """Response from web.fetch_page."""

    url: str
    canonical_url: str | None
    domain: str | None
    title: str | None
    visible_text: str
    http_status: int | None
    content_type: str | None
    fetch_status: str
    error_message: str | None


@dataclass
class NormalizeTextResponse:
    """Response from web.normalize_text."""

    normalized_text: str
    text_hash: str


def _post_with_retry(
    path: str,
    payload: dict,
    *,
    label: str,
    max_retries: int | None = None,
    backoff_base: float | None = None,
    timeout: float | None = None,
) -> dict:
    """POST to the MCP server with exponential backoff on transient failures.

    Args:
        path: URL path relative to the MCP server base URL (e.g. '/tools/web.search').
        payload: JSON-serialisable request body.
        label: Short description for log messages.
        max_retries: Override settings.max_retries.
        backoff_base: Override settings.backoff_base.
        timeout: Override settings.request_timeout.

    Returns:
        Parsed JSON response dict.

    Raises:
        RuntimeError: If all retries are exhausted.
    """
    _max = max_retries if max_retries is not None else settings.max_retries
    _base = backoff_base if backoff_base is not None else settings.backoff_base
    _timeout = timeout if timeout is not None else settings.request_timeout
    url = f"{settings.mcp_server_url}{path}"
    last_exc: Exception | None = None

    for attempt in range(_max):
        try:
            with httpx.Client(timeout=_timeout) as client:
                resp = client.post(url, json=payload)

            if resp.status_code in _RETRYABLE_STATUSES and attempt < _max - 1:
                wait = _base * (2 ** attempt)
                log.warning(
                    "MCP %s got HTTP %d, retrying in %.1fs (attempt %d/%d)",
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
                    "MCP %s transport error, retrying in %.1fs (attempt %d/%d): %s",
                    label, wait, attempt + 1, _max, exc,
                )
                time.sleep(wait)
            else:
                log.error("MCP %s failed after %d attempts: %s", label, _max, exc)

    raise RuntimeError(
        f"MCP {label} failed after {_max} attempts"
    ) from last_exc


def search(query: str, max_results: int | None = None) -> SearchResponse:
    """Call web.search and return ranked URL results.

    When all retry attempts fail with a ``TimeoutException`` the function
    raises a ``RuntimeError`` (as normal) **and** emits a WARNING that the
    DuckDuckGo rate limit is likely active.

    Args:
        query: Search query string.
        max_results: Override max results (uses settings default if None).

    Returns:
        A ``SearchResponse`` with ranked result items.

    Raises:
        RuntimeError: If the MCP server cannot be reached or all retries fail.
    """
    n = max_results if max_results is not None else settings.max_results_per_query
    try:
        data = _post_with_retry(
            "/tools/web.search",
            {"query": query, "max_results": n},
            label="web.search",
            # Search uses a tighter timeout and fewer retries: DuckDuckGo
            # rate limits don't clear within seconds, so retrying immediately
            # only multiplies the wait.  The MCP server's _SEARCH_TIMEOUT is
            # 8 s; we allow 12 s so the server can return a 500 before the
            # client fires its own timeout.
            timeout=12.0,
            max_retries=1,
        )
    except RuntimeError as exc:
        # Detect rate-limit pattern: all retries failed with timeouts.
        cause = exc.__cause__
        if isinstance(cause, httpx.TimeoutException) or (
            cause is None and "timed out" in str(exc).lower()
        ):
            log.warning(
                "RATE LIMIT LIKELY - all web.search retries timed out for query %r. "
                "DuckDuckGo is probably rate-limiting this container IP. "
                "Wait 30-60 minutes before the next run, or set "
                "SEARCH_PROVIDER=stub in the MCP server environment for testing.",
                query,
            )
        raise
    return SearchResponse(
        query=data["query"],
        provider=data["provider"],
        results=[
            SearchResultItem(
                rank=r["rank"],
                title=r.get("title"),
                url=r["url"],
                snippet=r.get("snippet"),
            )
            for r in data.get("results", [])
        ],
    )


def fetch_page(url: str) -> FetchPageResponse:
    """Call web.fetch_page and return the visible text and metadata.

    Args:
        url: URL to fetch.

    Returns:
        A ``FetchPageResponse`` with visible text and fetch metadata.
    """
    data = _post_with_retry(
        "/tools/web.fetch_page",
        {"url": url},
        label="web.fetch_page",
    )
    return FetchPageResponse(
        url=data["url"],
        canonical_url=data.get("canonical_url"),
        domain=data.get("domain"),
        title=data.get("title"),
        visible_text=data.get("visible_text", ""),
        http_status=data.get("http_status"),
        content_type=data.get("content_type"),
        fetch_status=data.get("fetch_status", "success"),
        error_message=data.get("error_message"),
    )


def normalize_text(text: str) -> NormalizeTextResponse:
    """Call web.normalize_text and return normalised text with hash.

    Args:
        text: Raw visible text to normalise.

    Returns:
        A ``NormalizeTextResponse`` with the normalised text and SHA-256 hash.
    """
    data = _post_with_retry(
        "/tools/web.normalize_text",
        {"text": text},
        label="web.normalize_text",
    )
    return NormalizeTextResponse(
        normalized_text=data["normalized_text"],
        text_hash=data["text_hash"],
    )
