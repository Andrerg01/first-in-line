"""Shared city/state normalization helpers for dedup candidate selection."""

from __future__ import annotations

from app.models.events import Event


def normalize_location_value(value: str | None) -> str | None:
    """Trim and lowercase a location value, preserving ``None``."""
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def is_location_match(event: Event, candidate: Event) -> bool:
    """Apply the shared city/state gating used for duplicate candidate lookup."""
    event_state = normalize_location_value(event.state)
    candidate_state = normalize_location_value(candidate.state)
    if event_state and candidate_state != event_state:
        return False

    event_city = normalize_location_value(event.city)
    candidate_city = normalize_location_value(candidate.city)
    if event_city:
        if candidate_city is None:
            return False
        if event_city not in candidate_city:
            return False
    return True