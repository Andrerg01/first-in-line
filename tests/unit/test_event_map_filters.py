"""Unit tests for Phase 7 event service map/date/geo filter logic."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException

from app.models.events import Event
from app.repositories.event_repository import _distance_miles
from app.services import event_service


def _make_event(db, **kwargs) -> Event:
    defaults = dict(
        id=uuid.uuid4(),
        business_name="Phase7 Cafe",
        event_type="grand_opening",
        status="candidate",
    )
    defaults.update(kwargs)
    event = Event(**defaults)
    db.add(event)
    db.flush()
    return event


# ---------------------------------------------------------------------------
# _distance_miles helper
# ---------------------------------------------------------------------------

class TestDistanceMiles:
    def test_same_point_is_zero(self):
        assert _distance_miles(34.85, -82.39, 34.85, -82.39) == pytest.approx(0.0, abs=1e-6)

    def test_greenville_to_columbia_roughly_100_miles(self):
        # Greenville SC ≈ (34.8526, -82.394) → Columbia SC ≈ (34.0007, -81.0348)
        dist = _distance_miles(34.8526, -82.394, 34.0007, -81.0348)
        assert 95 < dist < 115

    def test_symmetric(self):
        a = _distance_miles(34.85, -82.39, 35.23, -80.84)
        b = _distance_miles(35.23, -80.84, 34.85, -82.39)
        assert a == pytest.approx(b, rel=1e-9)


# ---------------------------------------------------------------------------
# Date range filters
# ---------------------------------------------------------------------------

class TestListEventsDateFilters:
    def test_start_date_filter_excludes_earlier_events(self, db_session):
        _make_event(db_session, event_date=datetime(2026, 6, 1, tzinfo=timezone.utc))
        _make_event(db_session, event_date=datetime(2026, 7, 1, tzinfo=timezone.utc))
        result = event_service.list_events(db_session, start_date=date(2026, 7, 1))
        assert len(result) == 1
        assert result[0].event_date.date() == date(2026, 7, 1)

    def test_end_date_filter_excludes_later_events(self, db_session):
        _make_event(db_session, event_date=datetime(2026, 6, 1, tzinfo=timezone.utc))
        _make_event(db_session, event_date=datetime(2026, 7, 1, tzinfo=timezone.utc))
        result = event_service.list_events(db_session, end_date=date(2026, 6, 15))
        assert len(result) == 1
        assert result[0].event_date.date() == date(2026, 6, 1)

    def test_date_range_filters_both_ends(self, db_session):
        _make_event(db_session, event_date=datetime(2026, 5, 1, tzinfo=timezone.utc))
        _make_event(db_session, event_date=datetime(2026, 6, 15, tzinfo=timezone.utc))
        _make_event(db_session, event_date=datetime(2026, 8, 1, tzinfo=timezone.utc))
        result = event_service.list_events(
            db_session,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 7, 1),
        )
        assert len(result) == 1
        assert result[0].event_date.date() == date(2026, 6, 15)

    def test_invalid_date_range_raises_422(self, db_session):
        with pytest.raises(HTTPException) as exc_info:
            event_service.list_events(
                db_session,
                start_date=date(2026, 8, 1),
                end_date=date(2026, 7, 1),
            )
        assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# Radius filter validation
# ---------------------------------------------------------------------------

class TestListEventsRadiusValidation:
    def test_radius_without_lat_lon_raises_422(self, db_session):
        with pytest.raises(HTTPException) as exc_info:
            event_service.list_events(db_session, radius_miles=10.0)
        assert exc_info.value.status_code == 422

    def test_radius_without_lon_raises_422(self, db_session):
        with pytest.raises(HTTPException) as exc_info:
            event_service.list_events(db_session, lat=34.85, radius_miles=10.0)
        assert exc_info.value.status_code == 422

    def test_radius_with_lat_lon_is_valid(self, db_session):
        # No error raised; returns empty list since no events exist.
        result = event_service.list_events(
            db_session, lat=34.85, lon=-82.39, radius_miles=10.0
        )
        assert result == []


# ---------------------------------------------------------------------------
# geocoded_only flag
# ---------------------------------------------------------------------------

class TestListEventsGeocodedOnly:
    def test_geocoded_only_excludes_events_without_coords(self, db_session):
        _make_event(db_session, lat=34.85, lon=-82.39)
        _make_event(db_session)  # no lat/lon
        result = event_service.list_events(db_session, geocoded_only=True)
        assert len(result) == 1
        assert result[0].lat is not None

    def test_geocoded_only_false_returns_all(self, db_session):
        _make_event(db_session, lat=34.85, lon=-82.39)
        _make_event(db_session)
        result = event_service.list_events(db_session, geocoded_only=False)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Radius filtering
# ---------------------------------------------------------------------------

class TestListEventsRadiusFilter:
    def test_radius_filter_excludes_distant_events(self, db_session):
        # Greenville SC and Columbia SC are ~100 miles apart.
        _make_event(db_session, lat=34.8526, lon=-82.394)   # Greenville — in range
        _make_event(db_session, lat=34.0007, lon=-81.0348)  # Columbia — out of range

        result = event_service.list_events(
            db_session, lat=34.8526, lon=-82.394, radius_miles=20.0
        )
        assert len(result) == 1
        assert float(result[0].lat) == pytest.approx(34.8526, rel=1e-4)

    def test_radius_filter_includes_nearby_event(self, db_session):
        _make_event(db_session, lat=34.8526, lon=-82.394)
        _make_event(db_session, lat=34.85, lon=-82.39)  # ~0.3 miles away

        result = event_service.list_events(
            db_session, lat=34.8526, lon=-82.394, radius_miles=1.0
        )
        assert len(result) == 2
