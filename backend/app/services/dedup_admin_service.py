"""Business operations for duplicate review, merging, and retroactive scans."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.events import Event
from app.repositories import dedup_repository, event_repository, source_repository
from app.services.dedup_scoring import (
    DUPLICATE_THRESHOLD,
    SimilarityResult,
    normalize_business_name,
    score_pair,
)
from app.utils.dedup_location import is_location_match


def _best_match(event: Event, candidates: list[Event]) -> SimilarityResult | None:
    """Return the highest-scoring duplicate candidate, if any exist."""
    if not candidates:
        return None
    return max((score_pair(event, candidate) for candidate in candidates), key=lambda item: item.score)


def check_and_flag_duplicate(
    db: Session,
    event: Event,
    *,
    threshold: float = DUPLICATE_THRESHOLD,
) -> SimilarityResult | None:
    """Normalize a saved event, score nearby candidates, and flag if matched."""
    normalized_name = normalize_business_name(event.business_name)
    dedup_repository.set_normalized_name(db, event, normalized_name)
    if not normalized_name:
        dedup_repository.set_duplicate_flag(db, event, duplicate_of_id=None)
        return None

    candidates = dedup_repository.find_candidates_by_city_state(
        db,
        city=event.city,
        state=event.state,
        exclude_id=event.id,
    )
    best = _best_match(event, candidates)
    if best is not None and best.score >= threshold:
        dedup_repository.set_duplicate_flag(db, event, duplicate_of_id=best.event_id)
        return best

    dedup_repository.set_duplicate_flag(db, event, duplicate_of_id=None)
    return None


def get_conflicts(db: Session, event_a_id: uuid.UUID, event_b_id: uuid.UUID) -> dict:
    """Return a side-by-side claim comparison between two events."""
    event_a = dedup_repository.get_event_with_claims(db, event_a_id)
    event_b = dedup_repository.get_event_with_claims(db, event_b_id)
    if event_a is None:
        raise ValueError(f"Event {event_a_id} not found.")
    if event_b is None:
        raise ValueError(f"Event {event_b_id} not found.")

    def _claims_by_type(event: Event) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for claim in event.claims:
            grouped.setdefault(claim.claim_type, []).append(claim.claim_value or "")
        return grouped

    claims_a = _claims_by_type(event_a)
    claims_b = _claims_by_type(event_b)
    claim_types = sorted(set(claims_a) | set(claims_b))
    conflicts = [claim_type for claim_type in claim_types if claims_a.get(claim_type) != claims_b.get(claim_type)]
    return {
        "event_a": {"id": str(event_a_id), "business_name": event_a.business_name, "claims": claims_a},
        "event_b": {"id": str(event_b_id), "business_name": event_b.business_name, "claims": claims_b},
        "conflicting_claim_types": conflicts,
    }


def merge_events(
    db: Session,
    *,
    source_id: uuid.UUID,
    target_id: uuid.UUID,
    canonical_fields: dict[str, object],
) -> Event:
    """Merge one event into a canonical target and preserve its evidence."""
    if source_id == target_id:
        raise ValueError("source_id and target_id must differ.")

    source = event_repository.get_event_by_id(db, source_id)
    target = event_repository.get_event_by_id(db, target_id)
    if source is None:
        raise ValueError(f"Source event {source_id} not found.")
    if target is None:
        raise ValueError(f"Target event {target_id} not found.")

    for field, value in canonical_fields.items():
        setattr(target, field, value)

    for claim in list(source.claims):
        claim.event_id = target.id

    source_links = source_repository.get_sources_for_event(db, source.id)
    target_links = source_repository.get_sources_for_event(db, target.id)
    target_source_ids = {link.source_document_id for link in target_links}
    for link in source_links:
        if link.source_document_id in target_source_ids:
            source_repository.delete_event_source(db, link)
            continue
        source_repository.reassign_event_source(db, link, new_event_id=target.id)

    source.status = "merged"
    source.duplicate_of_id = target_id
    source.possible_duplicate = False
    target.normalized_business_name = normalize_business_name(target.business_name)
    db.flush()
    return target


def flag_duplicate(
    db: Session,
    *,
    event_id: uuid.UUID,
    duplicate_of_id: uuid.UUID | None,
) -> Event:
    """Manually set or clear a possible-duplicate flag."""
    event = event_repository.get_event_by_id(db, event_id)
    if event is None:
        raise ValueError(f"Event {event_id} not found.")
    if duplicate_of_id is not None:
        if event_id == duplicate_of_id:
            raise ValueError("event_id and duplicate_of_id must differ.")
        canonical = event_repository.get_event_by_id(db, duplicate_of_id)
        if canonical is None:
            raise ValueError(f"Canonical event {duplicate_of_id} not found.")
    dedup_repository.set_duplicate_flag(db, event, duplicate_of_id=duplicate_of_id)
    return event


def run_retroactive_scan(
    db: Session,
    *,
    threshold: float = DUPLICATE_THRESHOLD,
) -> dict[str, int]:
    """Re-run duplicate detection across existing events in chronological order."""
    events = dedup_repository.list_events_for_retroactive_scan(db)
    flagged = 0
    cleared = 0

    for index, event in enumerate(events):
        normalized_name = normalize_business_name(event.business_name)
        dedup_repository.set_normalized_name(db, event, normalized_name)
        if not normalized_name:
            if event.possible_duplicate or event.duplicate_of_id is not None:
                dedup_repository.set_duplicate_flag(db, event, duplicate_of_id=None)
                cleared += 1
            continue

        prior_events = [
            candidate
            for candidate in events[:index]
            if is_location_match(event, candidate)
        ]

        best = _best_match(event, prior_events)
        if best is not None and best.score >= threshold:
            if not event.possible_duplicate or event.duplicate_of_id != best.event_id:
                flagged += 1
            dedup_repository.set_duplicate_flag(db, event, duplicate_of_id=best.event_id)
            continue

        if event.possible_duplicate or event.duplicate_of_id is not None:
            dedup_repository.set_duplicate_flag(db, event, duplicate_of_id=None)
            cleared += 1

    return {"scanned": len(events), "flagged": flagged, "cleared": cleared}