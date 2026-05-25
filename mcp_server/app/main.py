"""MCP server — exposes the approved narrow-tool catalog as HTTP endpoints.

Tools implemented in this module and sub-modules:
- web.fetch_page    — fetch a URL and extract visible text
- web.normalize_text — normalize and SHA-256 hash visible text
- web.search        — search the web and return ranked URL results
- geo.geocode_address — geocode an address string (see tools/geocode.py)

Future tools:
- db.find_source_by_hash
- db.find_similar_events
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import os
import re
import socket
import time
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from fastapi import FastAPI
from pydantic import BaseModel, Field

from .tools.geocode import router as geocode_router

log = logging.getLogger(__name__)

app = FastAPI(title="Grand Opening Radar MCP Server", version="0.1.0")
app.include_router(geocode_router)

# Tools currently implemented and callable
TOOL_LIST = [
    "web.fetch_page",
    "web.normalize_text",
    "web.search",
    "geo.geocode_address",
]

# Planned tools — not yet implemented; kept here to document the roadmap.
# NOTE: MCP tools must be read-only or bounded narrow writes; any event
# creation/modification must go through the backend API, not MCP directly.
_PLANNED_TOOLS = [
    "db.find_source_by_hash",
    "db.find_similar_events",
]

# Search configuration
# Valid values:
#   duckduckgo       — DuckDuckGo only (free, no key, ~10 results/query)
#   brave            — Brave Search API only (requires BRAVE_SEARCH_API_KEY, up to 20 results)
#   duckduckgo+brave — DuckDuckGo first; Brave fallback when DDG returns 0 results
#   stub             — deterministic test stubs (no network)
_SEARCH_PROVIDER = os.environ.get("SEARCH_PROVIDER", "duckduckgo")  # see valid values above
_SEARCH_TIMEOUT = 8.0   # seconds for DDGS calls; kept short so rate-limit hangs fail fast

# Brave Search API (used as DuckDuckGo fallback when it returns 0 results)
_BRAVE_SEARCH_API_KEY = os.environ.get("BRAVE_SEARCH_API_KEY", "")
_BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
_BRAVE_SEARCH_TIMEOUT = 10.0
_BRAVE_MAX_RESULTS = 20       # Brave free-tier hard cap per request
_BRAVE_SEARCH_MAX_RETRIES = 3  # max attempts on HTTP 429
_BRAVE_SEARCH_RETRY_CAP = 5.0  # max seconds to wait on a rate-limit back-off

_FETCH_TIMEOUT = 15.0  # seconds
_MAX_TEXT_BYTES = 500_000  # guard against huge pages
_MAX_FETCH_RETRIES = 3  # total attempts per URL fetch
_FETCH_BACKOFF_BASE = 1.0  # seconds; wait = _FETCH_BACKOFF_BASE * 2**attempt

# HTTP status codes that indicate a transient server error worth retrying.
_RETRYABLE_TARGET_STATUSES = frozenset({429, 500, 502, 503, 504})
_RETRYABLE_FETCH_ERRORS = (
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.RemoteProtocolError,
    httpx.ReadError,
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class FetchPageRequest(BaseModel):
    """Request body for web.fetch_page."""

    url: str


class FetchPageResponse(BaseModel):
    """Structured result from a page fetch."""

    url: str
    canonical_url: str | None
    domain: str | None
    title: str | None
    visible_text: str
    http_status: int | None
    content_type: str | None
    fetch_status: str  # success | failed
    error_message: str | None


class NormalizeTextRequest(BaseModel):
    """Request body for web.normalize_text."""

    text: str = Field(max_length=600_000)


class NormalizeTextResponse(BaseModel):
    """Normalised text plus its SHA-256 hex digest."""

    normalized_text: str
    text_hash: str


class SearchRequest(BaseModel):
    """Request body for web.search."""

    query: str
    max_results: int = Field(default=10, ge=1, le=50)  # caller (worker) sets this from SCRAPER_MAX_RESULTS_PER_QUERY


class SearchResultItem(BaseModel):
    """A single search result entry."""

    rank: int
    title: str | None
    url: str
    snippet: str | None


class SearchResponse(BaseModel):
    """Ranked list of search results for a query."""

    query: str
    provider: str
    results: list[SearchResultItem]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_INTERNAL_HOSTS: frozenset[str] = frozenset(
    {"localhost", "postgres", "backend-api", "mcp-server", "worker"}
)


def _is_safe_url(url: str) -> tuple[bool, str]:
    """Validate URL scheme and block private/internal hosts to prevent SSRF.

    Args:
        url: URL string to validate.

    Returns:
        Tuple of (is_safe, reason). ``reason`` is empty when safe.
    """
    try:
        parsed = urlparse(url)
    except Exception as exc:  # pragma: no cover
        return False, f"Invalid URL: {exc}"

    if parsed.scheme not in ("http", "https"):
        return False, f"Scheme '{parsed.scheme}' is not allowed; only http and https."

    host = parsed.hostname
    if not host:
        return False, "URL must specify a host."

    if host.lower() in _INTERNAL_HOSTS:
        return False, f"Host '{host}' is not allowed (internal service)."

    try:
        addr = ipaddress.ip_address(host)
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
        ):
            return False, f"IP '{host}' resolves to a private/reserved range."
    except ValueError:
        # Not a bare IP literal — resolve the hostname and validate resolved IPs
        # to guard against DNS rebinding attacks.
        try:
            resolved = socket.getaddrinfo(host, None)
        except socket.gaierror:
            # Cannot resolve — reject rather than allow an unknown target.
            return False, f"Host '{host}' could not be resolved."
        for family, _type, _proto, _canonname, sockaddr in resolved:
            ip_str = sockaddr[0]
            try:
                resolved_addr = ipaddress.ip_address(ip_str)
                if (
                    resolved_addr.is_private
                    or resolved_addr.is_loopback
                    or resolved_addr.is_link_local
                    or resolved_addr.is_reserved
                    or resolved_addr.is_multicast
                ):
                    return (
                        False,
                        f"Host '{host}' resolves to private/reserved IP {ip_str}.",
                    )
            except ValueError:
                continue

    return True, ""


def _extract_visible_text(html: str) -> tuple[str, str | None]:
    """Parse HTML and return (visible_text, page_title).

    Removes script, style, and noscript elements, then collapses whitespace.

    Args:
        html: Raw HTML string.

    Returns:
        Tuple of (visible_text, title).
    """
    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None
    for tag in soup(["script", "style", "noscript", "head"]):
        tag.decompose()
    raw_text = soup.get_text(separator=" ", strip=True)
    return raw_text, title


def _normalize(text: str) -> str:
    """Collapse whitespace and strip leading/trailing spaces.

    Args:
        text: Raw visible text.

    Returns:
        Normalised text string.
    """
    return re.sub(r"\s+", " ", text).strip()


def _sha256(text: str) -> str:
    """Return the SHA-256 hex digest of a UTF-8 encoded string.

    Args:
        text: Text to hash.

    Returns:
        64-character lowercase hex string.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fetch_url_with_retry(
    url: str,
    headers: dict,
    max_retries: int = _MAX_FETCH_RETRIES,
    backoff_base: float = _FETCH_BACKOFF_BASE,
) -> httpx.Response:
    """Fetch a URL with exponential backoff on transient errors.

    Retries on connection/timeout errors and HTTP 429/5xx responses.
    Does not retry HTTP 4xx (deterministic client errors).

    Args:
        url: Target URL to GET.
        headers: Request headers to include.
        max_retries: Total number of attempts.
        backoff_base: Base seconds for exponential backoff.

    Returns:
        The ``httpx.Response`` from the last successful (or final) attempt.

    Raises:
        httpx.HTTPError: If all attempts fail due to a transport error.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            with httpx.Client(
                timeout=_FETCH_TIMEOUT, follow_redirects=True
            ) as client:
                resp = client.get(url, headers=headers)

            if resp.status_code in _RETRYABLE_TARGET_STATUSES and attempt < max_retries - 1:
                wait = backoff_base * (2 ** attempt)
                log.warning(
                    "fetch %s got HTTP %d, retrying in %.1fs (attempt %d/%d)",
                    url, resp.status_code, wait, attempt + 1, max_retries,
                )
                time.sleep(wait)
                continue

            return resp  # success, or final attempt with a retryable status

        except _RETRYABLE_FETCH_ERRORS as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                wait = backoff_base * (2 ** attempt)
                log.warning(
                    "fetch %s error, retrying in %.1fs (attempt %d/%d): %s",
                    url, wait, attempt + 1, max_retries, exc,
                )
                time.sleep(wait)
            else:
                log.warning(
                    "fetch %s failed after %d attempts: %s", url, max_retries, exc
                )

    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, str]:
    """Return MCP server health status for uptime checks."""
    return {"status": "ok"}


@app.get("/tools")
def tools() -> dict[str, list[str]]:
    """Return the list of approved narrow tools exposed by this MCP server."""
    return {"tools": TOOL_LIST}


@app.post("/tools/web.fetch_page", response_model=FetchPageResponse)
def fetch_page(body: FetchPageRequest) -> FetchPageResponse:
    """Fetch a URL and extract its visible text.

    Performs up to ``_MAX_FETCH_RETRIES`` GET requests with exponential
    backoff on transient errors. Only text/html responses are parsed; others
    are rejected.

    Args:
        body: Request containing the URL to fetch.

    Returns:
        A FetchPageResponse with visible text and fetch metadata.
    """
    safe, reason = _is_safe_url(body.url)
    if not safe:
        log.warning("fetch_page blocked unsafe URL %s: %s", body.url, reason)
        return FetchPageResponse(
            url=body.url,
            canonical_url=None,
            domain=None,
            title=None,
            visible_text="",
            http_status=None,
            content_type=None,
            fetch_status="failed",
            error_message=f"URL not allowed: {reason}",
        )

    parsed = urlparse(body.url)
    domain = parsed.netloc or None

    headers = {
        "User-Agent": (
            "GrandOpeningRadar/0.1 (+https://github.com/Andrerg01/grand-opening-radar)"
        ),
        "Accept": "text/html,application/xhtml+xml",
    }

    try:
        resp = _fetch_url_with_retry(body.url, headers=headers)
    except httpx.TimeoutException as exc:
        log.warning("Fetch timeout for %s: %s", body.url, exc)
        return FetchPageResponse(
            url=body.url,
            canonical_url=None,
            domain=domain,
            title=None,
            visible_text="",
            http_status=None,
            content_type=None,
            fetch_status="failed",
            error_message=f"Timeout: {exc}",
        )
    except httpx.HTTPError as exc:
        log.warning("Fetch error for %s: %s", body.url, exc)
        return FetchPageResponse(
            url=body.url,
            canonical_url=None,
            domain=domain,
            title=None,
            visible_text="",
            http_status=None,
            content_type=None,
            fetch_status="failed",
            error_message=str(exc),
        )

    content_type = resp.headers.get("content-type", "")
    canonical_url = str(resp.url)

    if resp.status_code >= 400:
        return FetchPageResponse(
            url=body.url,
            canonical_url=canonical_url,
            domain=domain,
            title=None,
            visible_text="",
            http_status=resp.status_code,
            content_type=content_type,
            fetch_status="failed",
            error_message=f"HTTP {resp.status_code}",
        )

    if "text/html" not in content_type:
        return FetchPageResponse(
            url=body.url,
            canonical_url=canonical_url,
            domain=domain,
            title=None,
            visible_text="",
            http_status=resp.status_code,
            content_type=content_type,
            fetch_status="failed",
            error_message=f"Non-HTML content-type: {content_type}",
        )

    html = resp.text[:_MAX_TEXT_BYTES]
    visible_text, title = _extract_visible_text(html)

    return FetchPageResponse(
        url=body.url,
        canonical_url=canonical_url,
        domain=domain,
        title=title,
        visible_text=visible_text,
        http_status=resp.status_code,
        content_type=content_type,
        fetch_status="success",
        error_message=None,
    )


@app.post("/tools/web.normalize_text", response_model=NormalizeTextResponse)
def normalize_text(body: NormalizeTextRequest) -> NormalizeTextResponse:
    """Normalise visible text and compute its SHA-256 hash.

    Collapses whitespace to single spaces and strips leading/trailing
    whitespace.  The hash is used for source-document deduplication.

    Args:
        body: Request containing the raw text string.

    Returns:
        A NormalizeTextResponse with normalised text and hash.
    """
    normalized = _normalize(body.text)
    return NormalizeTextResponse(
        normalized_text=normalized,
        text_hash=_sha256(normalized),
    )


def _search_duckduckgo(query: str, max_results: int) -> list[SearchResultItem]:
    """Perform a text search using DuckDuckGo and return ranked results.

    Uses the ``duckduckgo_search`` library which requires no API key.
    Returns an empty list on rate-limit or any search error so the pipeline
    can continue gracefully.

    Args:
        query: Search query string.
        max_results: Maximum number of results to return.

    Returns:
        A list of ``SearchResultItem`` ranked by position.
    """
    try:
        with DDGS(timeout=_SEARCH_TIMEOUT) as ddgs:
            raw = ddgs.text(query, max_results=max_results)
    except Exception as exc:  # noqa: BLE001
        # Rate-limits and transient errors should degrade gracefully so the
        # pipeline can mark the query as failed without a 500 response.
        msg = str(exc).lower()
        if "ratelimit" in msg or "rate limit" in msg or "too many" in msg:
            log.warning("DuckDuckGo RATE LIMIT for query %r: %s", query, exc)
        else:
            log.warning("DuckDuckGo search error for query %r: %s", query, exc)
        return []
    return [
        SearchResultItem(
            rank=i + 1,
            title=r.get("title"),
            url=r["href"],
            snippet=r.get("body"),
        )
        for i, r in enumerate(raw or [])
    ]


def _parse_brave_ratelimit_reset(reset_header: str | None) -> float:
    """Return the per-second window reset delay from Brave's X-RateLimit-Reset header.

    The header contains comma-separated values for each rate-limit window.
    The first value is always the per-second (burst) window reset, in seconds.
    Example: ``"1, 1419704"`` → returns ``1.0``.

    Clamps to [0.1, ``_BRAVE_SEARCH_RETRY_CAP``] so the caller never waits
    an unreasonable amount of time.

    Args:
        reset_header: Raw ``X-RateLimit-Reset`` header value, or ``None``.

    Returns:
        Seconds to wait before the per-second burst quota resets.
    """
    if not reset_header:
        return 1.0
    try:
        first = reset_header.split(",")[0].strip()
        seconds = float(first)
        return min(max(0.1, seconds), _BRAVE_SEARCH_RETRY_CAP)
    except (ValueError, IndexError):
        return 1.0


def _search_brave(query: str, max_results: int) -> list[SearchResultItem]:
    """Perform a web search using the Brave Search API.

    Retries up to ``_BRAVE_SEARCH_MAX_RETRIES`` times on HTTP 429, waiting the
    duration indicated by the ``X-RateLimit-Reset`` response header before each
    retry.  After a successful response, sleeps briefly when
    ``X-RateLimit-Remaining`` reports the per-second quota is exhausted so the
    next sequential call does not immediately trigger another 429.

    Requires ``BRAVE_SEARCH_API_KEY`` to be set; returns ``[]`` silently if not.

    Args:
        query: Search query string.
        max_results: Maximum number of results to return (capped at 20 for free tier).

    Returns:
        A list of ``SearchResultItem`` ranked by position, or empty on error.
    """
    if not _BRAVE_SEARCH_API_KEY:
        return []

    count = min(max_results, _BRAVE_MAX_RESULTS)
    req_headers = {
        "X-Subscription-Token": _BRAVE_SEARCH_API_KEY,
        "Accept": "application/json",
    }

    for attempt in range(_BRAVE_SEARCH_MAX_RETRIES):
        try:
            with httpx.Client(timeout=_BRAVE_SEARCH_TIMEOUT) as client:
                resp = client.get(
                    _BRAVE_SEARCH_URL,
                    params={"q": query, "count": count},
                    headers=req_headers,
                )
        except Exception as exc:  # noqa: BLE001
            log.warning("Brave Search network error for query %r: %s", query, exc)
            return []

        if resp.status_code == 429:
            wait = _parse_brave_ratelimit_reset(resp.headers.get("X-RateLimit-Reset"))
            if attempt < _BRAVE_SEARCH_MAX_RETRIES - 1:
                log.warning(
                    "Brave Search rate-limited for query %r; waiting %.1fs "
                    "(attempt %d/%d)",
                    query, wait, attempt + 1, _BRAVE_SEARCH_MAX_RETRIES,
                )
                time.sleep(wait)
                continue
            log.warning(
                "Brave Search rate-limited for query %r after %d attempts; "
                "returning empty",
                query, _BRAVE_SEARCH_MAX_RETRIES,
            )
            return []

        if resp.status_code != 200:
            log.warning("Brave Search HTTP %d for query %r", resp.status_code, query)
            return []

        # Successful response.  If the per-second quota is now exhausted,
        # sleep for the reset duration so the next sequential query does not
        # immediately hit a 429.
        remaining_header = resp.headers.get("X-RateLimit-Remaining", "")
        if remaining_header:
            try:
                per_second_remaining = int(remaining_header.split(",")[0].strip())
                if per_second_remaining == 0:
                    pause = _parse_brave_ratelimit_reset(
                        resp.headers.get("X-RateLimit-Reset")
                    )
                    log.debug(
                        "Brave per-second quota exhausted; pausing %.1fs before "
                        "next call (query %r)",
                        pause, query,
                    )
                    time.sleep(pause)
            except (ValueError, IndexError):
                pass

        try:
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            log.warning("Brave Search JSON parse error for query %r: %s", query, exc)
            return []

        raw = data.get("web", {}).get("results", [])
        return [
            SearchResultItem(
                rank=i + 1,
                title=r.get("title"),
                url=r.get("url", ""),
                snippet=r.get("description"),
            )
            for i, r in enumerate(raw)
        ]

    return []  # all retries exhausted


def _search_stub(query: str, max_results: int) -> list[SearchResultItem]:  # noqa: ARG001
    """Return a deterministic stub result set for testing without network calls.

    Args:
        query: Search query string (included in stub titles).
        max_results: Maximum number of stub results to return.

    Returns:
        A fixed list of ``SearchResultItem`` entries.
    """
    stubs = [
        ("Stub: Grand Opening Restaurant Greenville SC", "https://example.com/stub/1"),
        ("Stub: New Brewery Opening Downtown Greenville", "https://example.com/stub/2"),
        ("Stub: Food Truck Grand Opening Greenville", "https://example.com/stub/3"),
    ]
    return [
        SearchResultItem(
            rank=i + 1,
            title=f"{title} [{query}]",
            url=url,
            snippet=f"Stub snippet for result {i + 1}.",
        )
        for i, (title, url) in enumerate(stubs[:max_results])
    ]


@app.post("/tools/web.search", response_model=SearchResponse)
def web_search(body: SearchRequest) -> SearchResponse:
    """Search the web and return a ranked list of results.

    Provider is controlled by the ``SEARCH_PROVIDER`` environment variable:
    - ``duckduckgo``       — DuckDuckGo only (free, ~10 results)
    - ``brave``            — Brave Search API only (requires BRAVE_SEARCH_API_KEY)
    - ``duckduckgo+brave`` — DuckDuckGo first; Brave fallback if DDG returns 0
    - ``stub``             — deterministic stubs for testing

    Args:
        body: Request containing the query string and max_results cap.

    Returns:
        A SearchResponse with ranked result items.
    """
    provider = _SEARCH_PROVIDER

    if provider == "stub":
        results = _search_stub(body.query, body.max_results)

    elif provider == "brave":
        if not _BRAVE_SEARCH_API_KEY:
            log.warning(
                "SEARCH_PROVIDER=brave but BRAVE_SEARCH_API_KEY is not set; "
                "returning empty results for query %r",
                body.query,
            )
            results = []
        else:
            results = _search_brave(body.query, body.max_results)

    elif provider == "duckduckgo+brave":
        results = _search_duckduckgo(body.query, body.max_results)
        provider = "duckduckgo"
        if not results and _BRAVE_SEARCH_API_KEY:
            log.info(
                "DDG returned 0 results for %r — trying Brave fallback",
                body.query,
            )
            results = _search_brave(body.query, body.max_results)
            if results:
                provider = "brave"

    else:
        # default: duckduckgo only
        results = _search_duckduckgo(body.query, body.max_results)
        provider = "duckduckgo"

    log.info(
        "web.search query=%r provider=%s results=%d",
        body.query, provider, len(results),
    )
    return SearchResponse(query=body.query, provider=provider, results=results)


# Geocode tool is in mcp_server/app/tools/geocode.py — registered above via app.include_router.
