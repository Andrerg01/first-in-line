"""Deterministic scoring helpers for event deduplication."""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import NamedTuple

from app.models.events import Event

DUPLICATE_THRESHOLD: float = 0.75

_W_NAME: float = 0.60
_W_ADDR: float = 0.25
_W_DATE: float = 0.15
_DATE_WINDOW_DAYS: int = 30

_SUFFIXES: frozenset[str] = frozenset(
    {
        "llc",
        "inc",
        "corp",
        "ltd",
        "co",
        "company",
        "restaurant",
        "bar",
        "grill",
        "cafe",
        "bistro",
        "kitchen",
        "eatery",
        "lounge",
        "diner",
        "house",
        "grille",
        "food",
        "bbq",
        "barbeque",
        "brewery",
        "taproom",
        "market",
        "bakery",
    }
)


class SimilarityResult(NamedTuple):
    """Similarity comparison result between two events."""

    event_id: uuid.UUID
    score: float
    name_score: float
    address_score: float
    date_score: float


def normalize_business_name(name: str | None) -> str:
    """Return a normalized form of a business name for similarity comparison."""
    if not name:
        return ""

    normalized = unicodedata.normalize("NFKD", name)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    normalized = normalized.replace("'", "")
    normalized = re.sub(r"[^a-z0-9 ]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    changed = True
    while changed:
        changed = False
        for suffix in _SUFFIXES:
            if normalized == suffix:
                break
            if normalized.endswith(f" {suffix}"):
                normalized = normalized[: -(len(suffix) + 1)].strip()
                changed = True
                break
    return normalized


def _name_similarity(a: str, b: str) -> float:
    """Return Jaccard similarity over unigram and bigram name tokens."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    def _tokens(s: str) -> set[str]:
        words = s.split()
        unigrams: set[str] = set(words)
        bigrams: set[str] = {f"{words[i]} {words[i + 1]}" for i in range(len(words) - 1)}
        return unigrams | bigrams

    ta, tb = _tokens(a), _tokens(b)
    union = len(ta | tb)
    return len(ta & tb) / union if union else 0.0


def _address_similarity(a: str | None, b: str | None) -> float:
    """Return token-level Jaccard similarity over address strings."""
    if a is None and b is None:
        return 1.0
    if a is None or b is None:
        return 0.5

    def _norm(s: str) -> set[str]:
        s = re.sub(r"[^a-z0-9 ]+", " ", s.lower())
        return set(s.split())

    ta, tb = _norm(a), _norm(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.5
    union = len(ta | tb)
    return len(ta & tb) / union if union else 0.0


def _date_similarity(a: datetime | None, b: datetime | None) -> float:
    """Return date similarity with a 30-day perfect-match window."""
    if a is None and b is None:
        return 1.0
    if a is None or b is None:
        return 0.5

    def _as_aware(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    a = _as_aware(a)
    b = _as_aware(b)
    delta_days = abs((a - b).total_seconds()) / 86400
    if delta_days <= _DATE_WINDOW_DAYS:
        return 1.0
    if delta_days >= 2 * _DATE_WINDOW_DAYS:
        return 0.0
    return 1.0 - (delta_days - _DATE_WINDOW_DAYS) / _DATE_WINDOW_DAYS


def score_pair(candidate: Event, existing: Event) -> SimilarityResult:
    """Compute the composite similarity score between two events."""
    norm_a = candidate.normalized_business_name or normalize_business_name(candidate.business_name)
    norm_b = existing.normalized_business_name or normalize_business_name(existing.business_name)
    name_score = _name_similarity(norm_a, norm_b)
    address_score = _address_similarity(candidate.address, existing.address)
    date_score = _date_similarity(candidate.event_date, existing.event_date)
    composite = _W_NAME * name_score + _W_ADDR * address_score + _W_DATE * date_score
    return SimilarityResult(
        event_id=existing.id,
        score=composite,
        name_score=name_score,
        address_score=address_score,
        date_score=date_score,
    )