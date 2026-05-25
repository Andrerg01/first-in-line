"""Geocode service — resolves lat/lon for events via the MCP geo.geocode_address tool.

Keeps geocoding logic in one place; the ingest service and admin bulk-geocode
action both delegate here.  All network calls are best-effort: a failed
geocode never aborts the calling pipeline.
"""

from __future__ import annotations

import logging
import uuid

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.events import Event
from app.repositories import event_repository

log = logging.getLogger(__name__)

_GEOCODE_TIMEOUT = 12.0
_MAX_UNGEOODED_BATCH = 500  # safety cap on bulk-geocode runs


def _build_address_query(event: Event) -> str | None:
    """Construct a geocoding query string from event address fields.

    Prefers the full ``address`` field; falls back to city + state so that
    events without a street address can still be placed on the map at the
    city level.

    Args:
        event: Event ORM instance.

    Returns:
        A non-empty query string, or ``None`` if there is nothing to geocode.
    """
    parts: list[str] = []
    if event.address:
        parts.append(event.address)
    if event.city:
        parts.append(event.city)
    if event.state:
        parts.append(event.state)
    if not parts:
        return None
    return ", ".join(parts)


def _call_mcp_geocode(address: str) -> dict:
    """POST to the MCP geo.geocode_address endpoint.

    Args:
        address: Free-form address string.

    Returns:
        Parsed JSON response dict with ``lat``, ``lon``, etc.

    Raises:
        httpx.HTTPError: On network or server failure.
    """
    endpoint = f"{settings.mcp_server_url}/tools/geo.geocode_address"
    with httpx.Client(timeout=_GEOCODE_TIMEOUT) as client:
        resp = client.post(endpoint, json={"address": address})
    resp.raise_for_status()
    return resp.json()


def geocode_event(db: Session, event: Event) -> bool:
    """Attempt to geocode a single event and persist the result.

    Skips the event if it already has coordinates or if no address
    information is available.  A failed geocode is logged as a warning
    but never raises so the calling pipeline can continue.

    Args:
        db: Active database session.
        event: Event ORM instance to geocode.

    Returns:
        ``True`` if lat/lon were updated, ``False`` otherwise.
    """
    if event.lat is not None and event.lon is not None:
        return False  # already geocoded

    query = _build_address_query(event)
    if not query:
        log.debug("geocode_event skip event %s — no address fields", event.id)
        return False

    try:
        result = _call_mcp_geocode(query)
    except Exception as exc:  # noqa: BLE001
        log.warning("geocode_event MCP call failed for event %s (%r): %s", event.id, query, exc)
        return False

    lat = result.get("lat")
    lon = result.get("lon")
    if lat is None or lon is None:
        log.debug(
            "geocode_event no result for event %s (%r): %s",
            event.id, query, result.get("error"),
        )
        return False

    event_repository.update_event_geo(db, event, lat=float(lat), lon=float(lon))
    log.info("geocode_event event %s geocoded to (%.6f, %.6f)", event.id, lat, lon)
    return True


def geocode_ungeocoded_events(db: Session) -> dict[str, int]:
    """Geocode all events that are missing lat/lon coordinates.

    Fetches up to ``_MAX_UNGEOODED_BATCH`` events per call, attempts
    geocoding for each, and returns aggregate counts.

    Args:
        db: Active database session.

    Returns:
        Dict with keys ``attempted``, ``geocoded``, ``skipped``.
    """
    events = event_repository.get_ungeocoded_events(db, limit=_MAX_UNGEOODED_BATCH)
    attempted = 0
    geocoded = 0
    skipped = 0

    for event in events:
        query = _build_address_query(event)
        if not query:
            # The repository pre-filters for address/city, but guard defensively.
            skipped += 1
            continue
        attempted += 1
        success = geocode_event(db, event)
        if success:
            geocoded += 1

    db.commit()
    log.info(
        "geocode_ungeocoded_events: attempted=%d geocoded=%d skipped=%d",
        attempted, geocoded, skipped,
    )
    return {"attempted": attempted, "geocoded": geocoded, "skipped": skipped}
