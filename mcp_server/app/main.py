"""MCP server — exposes the approved narrow-tool catalog as HTTP endpoints.

Tools implemented in this module:
- web.fetch_page   — fetch a URL and extract visible text
- web.normalize_text — normalize and SHA-256 hash visible text

Future tools (LangGraph Phase 5):
- web.search
- geo.geocode_address
- db.find_source_by_hash
- db.find_similar_events
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import re
import socket
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI
from pydantic import BaseModel

log = logging.getLogger(__name__)

app = FastAPI(title="Grand Opening Radar MCP Server", version="0.1.0")

# Tools currently implemented and callable
TOOL_LIST = [
    "web.fetch_page",
    "web.normalize_text",
]

# Planned tools — not yet implemented; kept here to document the roadmap.
# NOTE: MCP tools must be read-only or bounded narrow writes; any event
# creation/modification must go through the backend API, not MCP directly.
_PLANNED_TOOLS = [
    "web.search",
    "geo.geocode_address",
    "db.find_source_by_hash",
    "db.find_similar_events",
]

_FETCH_TIMEOUT = 15.0  # seconds
_MAX_TEXT_BYTES = 500_000  # guard against huge pages

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

    text: str


class NormalizeTextResponse(BaseModel):
    """Normalised text plus its SHA-256 hex digest."""

    normalized_text: str
    text_hash: str


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

    Performs a single GET request with a sensible timeout and content-type
    check.  Only text/html responses are parsed; others are rejected.

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
        with httpx.Client(timeout=_FETCH_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(body.url, headers=headers)
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
