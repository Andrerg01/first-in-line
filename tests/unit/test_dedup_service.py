"""Unit tests for the dedup service — normalization, scoring, and flagging."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.models.events import Event
from app.repositories import dedup_repository
from app.services.dedup_service import (
    DUPLICATE_THRESHOLD,
    SimilarityResult,
    _address_similarity,
    _date_similarity,
    _name_similarity,
    check_and_flag_duplicate,
    get_conflicts,
    merge_events,
    normalize_business_name,
    run_retroactive_scan,
    score_pair,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event(db, *, business_name: str | None = None, city: str = "Greenville",
           state: str = "SC", address: str | None = None,
           event_date: datetime | None = None,
           status: str = "candidate", **kwargs) -> Event:
    e = Event(
        id=uuid.uuid4(),
        business_name=business_name,
        event_type="grand_opening",
        status=status,
        city=city,
        state=state,
        address=address,
        event_date=event_date,
        **kwargs,
    )
    db.add(e)
    db.flush()
    return e


_DT = datetime(2026, 6, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# normalize_business_name
# ---------------------------------------------------------------------------


class TestNormalizeBusinessName:
    def test_lowercases(self):
        assert normalize_business_name("Salty Dog LLC") == "salty dog"

    def test_strips_accents(self):
        result = normalize_business_name("Café São Paulo")
        assert "cafe" in result
        assert "sao" in result

    def test_removes_punctuation(self):
        assert normalize_business_name("O'Brien's Pub!") == "obriens pub"

    def test_strips_common_suffix_restaurant(self):
        assert normalize_business_name("The Corner Restaurant") == "the corner"

    def test_strips_llc(self):
        assert normalize_business_name("Main Street Brewing LLC") == "main street brewing"

    def test_strips_multiple_trailing_suffixes(self):
        # "brewery" then "llc" both stripped iteratively
        result = normalize_business_name("River Brewery LLC")
        assert result == "river"

    def test_empty_string_returns_empty(self):
        assert normalize_business_name("") == ""

    def test_none_returns_empty(self):
        assert normalize_business_name(None) == ""

    def test_preserves_unique_name(self):
        result = normalize_business_name("Zaxby's")
        assert result == "zaxbys"

    def test_collapses_whitespace(self):
        assert normalize_business_name("  Big   Sky   ") == "big sky"


# ---------------------------------------------------------------------------
# Sub-score helpers
# ---------------------------------------------------------------------------


class TestNameSimilarity:
    def test_identical(self):
        assert _name_similarity("salty dog", "salty dog") == 1.0

    def test_completely_different(self):
        score = _name_similarity("alpha bravo", "zeta omega")
        assert score < 0.1

    def test_partial_overlap(self):
        score = _name_similarity("corner cafe", "corner grill")
        assert 0.1 < score < 0.9

    def test_empty_both(self):
        assert _name_similarity("", "") == 1.0

    def test_one_empty(self):
        assert _name_similarity("", "something") == 0.0


class TestAddressSimilarity:
    def test_both_none(self):
        assert _address_similarity(None, None) == 1.0

    def test_one_none_returns_neutral(self):
        score = _address_similarity(None, "123 Main St")
        assert score == 0.5

    def test_identical(self):
        assert _address_similarity("123 Main St", "123 Main St") == 1.0

    def test_partial_overlap(self):
        score = _address_similarity("123 Main St Greenville", "123 Main Street")
        assert score > 0.3

    def test_completely_different(self):
        score = _address_similarity("100 Oak Ave", "500 Pine Blvd Columbia")
        assert score < 0.5


class TestDateSimilarity:
    def test_both_none(self):
        assert _date_similarity(None, None) == 1.0

    def test_one_none_returns_neutral(self):
        assert _date_similarity(None, _DT) == 0.5

    def test_same_date(self):
        assert _date_similarity(_DT, _DT) == 1.0

    def test_within_window(self):
        from datetime import timedelta
        dt2 = datetime(2026, 6, 20, tzinfo=timezone.utc)
        assert _date_similarity(_DT, dt2) == 1.0

    def test_beyond_double_window(self):
        from datetime import timedelta
        dt2 = datetime(2026, 9, 1, tzinfo=timezone.utc)  # >60 days out
        assert _date_similarity(_DT, dt2) == 0.0

    def test_mid_range_decay(self):
        from datetime import timedelta
        dt2 = datetime(2026, 7, 16, tzinfo=timezone.utc)  # ~45 days out
        score = _date_similarity(_DT, dt2)
        assert 0.0 < score < 1.0


# ---------------------------------------------------------------------------
# score_pair
# ---------------------------------------------------------------------------


class TestScorePair:
    def test_identical_events_score_near_one(self, db_session):
        a = _event(db_session, business_name="Salty Dog", address="100 Main St", event_date=_DT)
        b = _event(db_session, business_name="Salty Dog", address="100 Main St", event_date=_DT)
        a.normalized_business_name = normalize_business_name(a.business_name)
        b.normalized_business_name = normalize_business_name(b.business_name)
        result = score_pair(a, b)
        assert isinstance(result, SimilarityResult)
        assert result.score >= 0.9

    def test_completely_different_events_score_low(self, db_session):
        a = _event(db_session, business_name="Alpha Cafe", address="1 Oak Ave",
                   event_date=datetime(2026, 1, 1, tzinfo=timezone.utc))
        b = _event(db_session, business_name="Zeta Grill", address="99 Pine Blvd",
                   event_date=datetime(2027, 6, 1, tzinfo=timezone.utc))
        a.normalized_business_name = normalize_business_name(a.business_name)
        b.normalized_business_name = normalize_business_name(b.business_name)
        result = score_pair(a, b)
        assert result.score < 0.4


# ---------------------------------------------------------------------------
# check_and_flag_duplicate
# ---------------------------------------------------------------------------


class TestCheckAndFlagDuplicate:
    def test_flags_near_duplicate(self, db_session):
        # Canonical event already in DB
        canonical = _event(
            db_session,
            business_name="Salty Dog Cafe",
            address="100 Main St",
            event_date=_DT,
            status="verified",
        )
        canonical.normalized_business_name = normalize_business_name(canonical.business_name)
        db_session.flush()

        # New candidate — same name, address, date
        candidate = _event(
            db_session,
            business_name="Salty Dog Café",  # accent variant
            address="100 Main St",
            event_date=_DT,
            status="candidate",
        )

        result = check_and_flag_duplicate(db_session, candidate)

        assert result is not None
        assert result.event_id == canonical.id
        assert result.score >= DUPLICATE_THRESHOLD
        assert candidate.possible_duplicate is True
        assert candidate.duplicate_of_id == canonical.id

    def test_no_flag_for_distinct_event(self, db_session):
        _event(
            db_session,
            business_name="Zeta Grill",
            address="99 Pine Blvd",
            event_date=datetime(2027, 1, 1, tzinfo=timezone.utc),
            status="verified",
        )
        candidate = _event(
            db_session,
            business_name="Alpha Bakery",
            address="5 Oak Ave",
            event_date=_DT,
            status="candidate",
        )
        result = check_and_flag_duplicate(db_session, candidate)
        assert result is None
        assert candidate.possible_duplicate is False

    def test_no_flag_when_no_business_name(self, db_session):
        _event(db_session, business_name="Some Cafe", status="verified")
        candidate = _event(db_session, business_name=None, status="candidate")
        result = check_and_flag_duplicate(db_session, candidate)
        assert result is None

    def test_sets_normalized_name_on_candidate(self, db_session):
        candidate = _event(db_session, business_name="River Brewing LLC", status="candidate")
        check_and_flag_duplicate(db_session, candidate)
        assert candidate.normalized_business_name == normalize_business_name("River Brewing LLC")


# ---------------------------------------------------------------------------
# merge_events
# ---------------------------------------------------------------------------


class TestMergeEvents:
    def test_merge_reassigns_claims_and_marks_source(self, db_session):
        from app.models.claims import EventClaim
        from app.models.sources import SourceDocument

        # Create minimal source doc
        src_doc = SourceDocument(
            id=uuid.uuid4(),
            url="https://example.com/test",
            fetch_status="success",
        )
        db_session.add(src_doc)
        db_session.flush()

        source = _event(db_session, business_name="Salty Dog Cafe (old)")
        target = _event(db_session, business_name="Salty Dog Cafe", status="verified")

        # Attach a claim to source
        claim = EventClaim(
            id=uuid.uuid4(),
            event_id=source.id,
            source_document_id=src_doc.id,
            claim_type="business_name",
            claim_value="Salty Dog Cafe (old)",
        )
        db_session.add(claim)
        db_session.flush()

        canonical = merge_events(
            db_session,
            source_id=source.id,
            target_id=target.id,
            canonical_fields={"business_name": "Salty Dog Cafe (merged)"},
        )

        assert canonical.id == target.id
        assert canonical.business_name == "Salty Dog Cafe (merged)"
        assert source.status == "merged"
        assert source.duplicate_of_id == target.id
        assert claim.event_id == target.id  # claim reassigned

    def test_merge_raises_on_same_ids(self, db_session):
        ev = _event(db_session, business_name="Foo")
        with pytest.raises(ValueError, match="must differ"):
            merge_events(db_session, source_id=ev.id, target_id=ev.id, canonical_fields={})

    def test_merge_raises_on_missing_event(self, db_session):
        ev = _event(db_session, business_name="Foo")
        with pytest.raises(ValueError):
            merge_events(
                db_session,
                source_id=ev.id,
                target_id=uuid.uuid4(),
                canonical_fields={},
            )


# ---------------------------------------------------------------------------
# get_conflicts
# ---------------------------------------------------------------------------


class TestGetConflicts:
    def test_detects_conflicting_claim_types(self, db_session):
        from app.models.claims import EventClaim
        from app.models.sources import SourceDocument

        src_doc = SourceDocument(
            id=uuid.uuid4(), url="https://x.com/test", fetch_status="success"
        )
        db_session.add(src_doc)
        db_session.flush()

        a = _event(db_session, business_name="Foo")
        b = _event(db_session, business_name="Bar")

        for ev, val in [(a, "2026-06-01"), (b, "2026-07-01")]:
            db_session.add(
                EventClaim(
                    id=uuid.uuid4(),
                    event_id=ev.id,
                    source_document_id=src_doc.id,
                    claim_type="event_date",
                    claim_value=val,
                )
            )
        db_session.flush()

        result = get_conflicts(db_session, a.id, b.id)

        assert "event_date" in result["conflicting_claim_types"]
        assert result["event_a"]["id"] == str(a.id)
        assert result["event_b"]["id"] == str(b.id)

    def test_no_conflicts_when_claims_match(self, db_session):
        from app.models.claims import EventClaim
        from app.models.sources import SourceDocument

        src_doc = SourceDocument(
            id=uuid.uuid4(), url="https://x.com/same", fetch_status="success"
        )
        db_session.add(src_doc)
        db_session.flush()

        a = _event(db_session, business_name="Foo")
        b = _event(db_session, business_name="Foo")

        for ev in (a, b):
            db_session.add(
                EventClaim(
                    id=uuid.uuid4(),
                    event_id=ev.id,
                    source_document_id=src_doc.id,
                    claim_type="business_name",
                    claim_value="Foo",
                )
            )
        db_session.flush()

        result = get_conflicts(db_session, a.id, b.id)
        assert result["conflicting_claim_types"] == []


# ---------------------------------------------------------------------------
# run_retroactive_scan
# ---------------------------------------------------------------------------


class TestRunRetroactiveScan:
    def test_flags_existing_duplicate_pair(self, db_session):
        older = _event(
            db_session,
            business_name="Enlo Restaurant",
            city="Greenville",
            state="SC",
            address="123 Main St",
            event_date=_DT,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            status="verified",
        )
        newer = _event(
            db_session,
            business_name="Enlo",
            city="Greenville",
            state="SC",
            address="123 Main Street",
            event_date=_DT,
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            status="candidate",
        )

        result = run_retroactive_scan(db_session)

        assert result["scanned"] >= 2
        assert result["flagged"] >= 1
        assert newer.possible_duplicate is True
        assert newer.duplicate_of_id == older.id

    def test_clears_stale_duplicate_flag_when_no_match(self, db_session):
        event = _event(
            db_session,
            business_name="Solo Business",
            city="Greenville",
            state="SC",
            status="candidate",
            possible_duplicate=True,
            duplicate_of_id=uuid.uuid4(),
        )

        result = run_retroactive_scan(db_session)

        assert result["cleared"] >= 1
        assert event.possible_duplicate is False
        assert event.duplicate_of_id is None

    def test_does_not_match_prior_event_missing_location(self, db_session):
        _event(
            db_session,
            business_name="Enlo Restaurant",
            city=None,
            state=None,
            address="123 Main St",
            event_date=_DT,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            status="verified",
        )
        newer = _event(
            db_session,
            business_name="Enlo",
            city="Greenville",
            state="SC",
            address="123 Main Street",
            event_date=_DT,
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            status="candidate",
        )

        result = run_retroactive_scan(db_session)

        assert result["flagged"] == 0
        assert newer.possible_duplicate is False

    def test_leaves_existing_correct_flag_unchanged(self, db_session):
        older = _event(
            db_session,
            business_name="Enlo Restaurant",
            city="Greenville",
            state="SC",
            address="123 Main St",
            event_date=_DT,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            status="verified",
        )
        newer = _event(
            db_session,
            business_name="Enlo",
            city="Greenville",
            state="SC",
            address="123 Main Street",
            event_date=_DT,
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            status="candidate",
            possible_duplicate=True,
            duplicate_of_id=older.id,
        )

        result = run_retroactive_scan(db_session)

        assert result["flagged"] == 0
        assert result["cleared"] == 0
        assert newer.possible_duplicate is True
        assert newer.duplicate_of_id == older.id

    def test_whitespace_padded_city_matches_same_as_live_path(self, db_session):
        older = _event(
            db_session,
            business_name="Enlo Restaurant",
            city="Greenville",
            state="SC",
            address="123 Main St",
            event_date=_DT,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            status="verified",
        )
        newer = _event(
            db_session,
            business_name="Enlo",
            city=" Greenville ",
            state="SC",
            address="123 Main Street",
            event_date=_DT,
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            status="candidate",
        )

        live_result = check_and_flag_duplicate(db_session, newer)
        dedup_repository.set_duplicate_flag(db_session, newer, duplicate_of_id=None)
        newer.possible_duplicate = False

        retro_result = run_retroactive_scan(db_session)

        assert live_result is not None
        assert retro_result["flagged"] >= 1
        assert newer.possible_duplicate is True
        assert newer.duplicate_of_id == older.id

    def test_whitespace_padded_state_matches_same_as_live_path(self, db_session):
        older = _event(
            db_session,
            business_name="Enlo Restaurant",
            city="Greenville",
            state=" SC ",
            address="123 Main St",
            event_date=_DT,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            status="verified",
        )
        newer = _event(
            db_session,
            business_name="Enlo",
            city="Greenville",
            state="SC",
            address="123 Main Street",
            event_date=_DT,
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            status="candidate",
        )

        live_result = check_and_flag_duplicate(db_session, newer)
        dedup_repository.set_duplicate_flag(db_session, newer, duplicate_of_id=None)
        newer.possible_duplicate = False

        retro_result = run_retroactive_scan(db_session)

        assert live_result is not None
        assert retro_result["flagged"] >= 1
        assert newer.possible_duplicate is True
        assert newer.duplicate_of_id == older.id
