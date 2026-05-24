"""URL canonicalization utilities.

Provides deterministic URL normalization before deduplication checks so that
URLs that resolve to the same page are not fetched more than once per run.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# UTM and common tracking parameters to strip from query strings.
_TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
        "msclkid",
        "mc_cid",
        "mc_eid",
        "ref",
        "_ga",
    }
)


def canonicalize_url(url: str) -> str:
    """Return a canonical form of a URL for deduplication.

    Transformations applied:
    - Lowercase the scheme and host.
    - Remove default ports (80 for http, 443 for https).
    - Strip trailing slash from the path (unless it is the root path).
    - Remove known tracking query parameters.
    - Sort remaining query parameters for stable comparison.
    - Remove fragment (``#``).

    Args:
        url: Raw URL string.

    Returns:
        Canonical URL string, or the original URL if parsing fails.
    """
    try:
        parsed = urlparse(url)
    except Exception:  # noqa: BLE001
        return url

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Strip default ports.
    if scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]
    elif scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]

    # Normalise path — remove trailing slash except for root.
    path = parsed.path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Filter tracking params; sort the remainder.
    if parsed.query:
        qs = parse_qs(parsed.query, keep_blank_values=True)
        filtered = {k: v for k, v in qs.items() if k.lower() not in _TRACKING_PARAMS}
        query = urlencode(sorted(filtered.items()), doseq=True)
    else:
        query = ""

    return urlunparse((scheme, netloc, path, parsed.params, query, ""))


def is_valid_http_url(url: str) -> bool:
    """Return True if the URL has an http or https scheme and a non-empty host.

    Args:
        url: URL string to validate.

    Returns:
        True when the URL is a valid HTTP/HTTPS URL.
    """
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:  # noqa: BLE001
        return False
