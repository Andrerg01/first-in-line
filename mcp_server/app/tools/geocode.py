"""Geocode tool — implements the geo.geocode_address MCP endpoint.

Provider is selected by the ``GEOCODE_PROVIDER`` environment variable:
- ``nominatim`` — Nominatim OpenStreetMap (free, no key; 1 req/sec usage policy)
- ``stub``      — deterministic stubs for testing without network access

Nominatim usage policy: https://operations.osmfoundation.org/policies/nominatim/
- Identify the application via User-Agent.
- Max one request per second; enforced via time.sleep after each call.
"""

from __future__ import annotations

import logging
import os
import time

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Valid values: nominatim | stub
_GEOCODE_PROVIDER = os.environ.get("GEOCODE_PROVIDER", "nominatim")
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_TIMEOUT = 10.0
_NOMINATIM_RATE_LIMIT_SLEEP = 1.0  # seconds between calls (Nominatim ToS)
_NOMINATIM_USER_AGENT = (
    "GrandOpeningRadar/0.1 (+https://github.com/Andrerg01/grand-opening-radar)"
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class GeocodeRequest(BaseModel):
    """Request body for geo.geocode_address."""

    address: str = Field(min_length=3, max_length=500)


class GeocodeResponse(BaseModel):
    """Geocode result with coordinates and provider metadata."""

    address: str
    lat: float | None
    lon: float | None
    normalized_address: str | None
    confidence: float | None
    provider: str
    error: str | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _geocode_nominatim(address: str) -> GeocodeResponse:
    """Geocode an address using the Nominatim OpenStreetMap API.

    Enforces the Nominatim usage policy: sleeps 1 second after each request
    and identifies the application via the User-Agent header.

    Args:
        address: Free-form address string to geocode.

    Returns:
        A ``GeocodeResponse`` with lat/lon, or a failed response on error.
    """
    try:
        with httpx.Client(timeout=_NOMINATIM_TIMEOUT) as client:
            resp = client.get(
                _NOMINATIM_URL,
                params={"q": address, "format": "json", "limit": 1},
                headers={"User-Agent": _NOMINATIM_USER_AGENT},
            )
        resp.raise_for_status()
        results = resp.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("Nominatim geocode failed for %r: %s", address, exc)
        return GeocodeResponse(
            address=address,
            lat=None,
            lon=None,
            normalized_address=None,
            confidence=None,
            provider="nominatim",
            error=str(exc),
        )
    finally:
        # Rate-limit compliance: sleep even on error so the caller cannot
        # trigger >1 req/sec by catching exceptions and retrying immediately.
        time.sleep(_NOMINATIM_RATE_LIMIT_SLEEP)

    if not results:
        return GeocodeResponse(
            address=address,
            lat=None,
            lon=None,
            normalized_address=None,
            confidence=None,
            provider="nominatim",
            error="No results found",
        )

    hit = results[0]
    return GeocodeResponse(
        address=address,
        lat=float(hit["lat"]),
        lon=float(hit["lon"]),
        normalized_address=hit.get("display_name"),
        confidence=float(hit.get("importance", 0.0)),
        provider="nominatim",
        error=None,
    )


def _geocode_stub(address: str) -> GeocodeResponse:
    """Return deterministic stub geocode results for testing without network.

    Addresses containing "greenville" or " sc" / ",sc" return a fixed
    Greenville, SC coordinate.  All other inputs return a no-result response.

    Args:
        address: Address string.

    Returns:
        A deterministic ``GeocodeResponse``.
    """
    lower = address.lower()
    if "greenville" in lower or " sc" in lower or ",sc" in lower:
        return GeocodeResponse(
            address=address,
            lat=34.8526,
            lon=-82.3940,
            normalized_address="Greenville, Greenville County, South Carolina, United States",
            confidence=0.85,
            provider="stub",
            error=None,
        )
    return GeocodeResponse(
        address=address,
        lat=None,
        lon=None,
        normalized_address=None,
        confidence=None,
        provider="stub",
        error="No stub match for address",
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/tools/geo.geocode_address", response_model=GeocodeResponse)
def geocode_address(body: GeocodeRequest) -> GeocodeResponse:
    """Geocode a free-form address string and return lat/lon coordinates.

    Provider is controlled by the ``GEOCODE_PROVIDER`` environment variable:
    - ``nominatim`` — Nominatim OSM (free, no key; 1 req/sec usage policy)
    - ``stub``      — deterministic stubs for testing (no network)

    Args:
        body: Request containing the address string.

    Returns:
        A ``GeocodeResponse`` with lat/lon coordinates and provider metadata.
    """
    if _GEOCODE_PROVIDER == "stub":
        result = _geocode_stub(body.address)
    else:
        result = _geocode_nominatim(body.address)

    log.info(
        "geo.geocode_address address=%r provider=%s found=%s",
        body.address, result.provider, result.lat is not None,
    )
    return result
