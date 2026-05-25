"""Integration tests for Phase 7 map/date/geo filter API extensions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.models.events import Event


def _insert_event(client, **kwargs):
    """Insert an event directly into the test DB via the app session factory."""
    from app.db import _get_session_factory  # noqa: PLC0415

    Session = _get_session_factory()
    with Session() as db:
        defaults = dict(
            id=uuid.uuid4(),
            business_name="Map Test Cafe",
            event_type="grand_opening",
            status="candidate",
            city="Greenville",
            state="SC",
        )
        defaults.update(kwargs)
        event = Event(**defaults)
        db.add(event)
        db.commit()
        db.refresh(event)
        return event.id


class TestDateFilterOnListEndpoint:
    def test_start_date_excludes_earlier_events(self, test_client):
        _insert_event(test_client, event_date=datetime(2026, 5, 1, tzinfo=timezone.utc))
        _insert_event(test_client, event_date=datetime(2026, 7, 1, tzinfo=timezone.utc))
        response = test_client.get("/api/events?start_date=2026-06-01")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["event_date"].startswith("2026-07")

    def test_end_date_excludes_later_events(self, test_client):
        _insert_event(test_client, event_date=datetime(2026, 5, 1, tzinfo=timezone.utc))
        _insert_event(test_client, event_date=datetime(2026, 7, 1, tzinfo=timezone.utc))
        response = test_client.get("/api/events?end_date=2026-06-01")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["event_date"].startswith("2026-05")

    def test_invalid_date_range_returns_422(self, test_client):
        response = test_client.get(
            "/api/events?start_date=2026-08-01&end_date=2026-07-01"
        )
        assert response.status_code == 422

    def test_radius_without_lat_lon_returns_422(self, test_client):
        response = test_client.get("/api/events?radius_miles=10")
        assert response.status_code == 422

    def test_radius_with_lat_lon_returns_200(self, test_client):
        response = test_client.get(
            "/api/events?lat=34.85&lon=-82.39&radius_miles=10"
        )
        assert response.status_code == 200


class TestMapEndpoint:
    def test_map_endpoint_returns_empty_when_no_geocoded_events(self, test_client):
        _insert_event(test_client)  # no lat/lon
        response = test_client.get("/api/events/map")
        assert response.status_code == 200
        assert response.json() == []

    def test_map_endpoint_returns_geocoded_events(self, test_client):
        _insert_event(test_client, lat=34.8526, lon=-82.394)
        _insert_event(test_client)  # no coords — excluded
        response = test_client.get("/api/events/map")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["lat"] is not None
        assert data[0]["lon"] is not None

    def test_map_endpoint_filters_by_status(self, test_client):
        _insert_event(test_client, lat=34.85, lon=-82.39, status="verified")
        _insert_event(test_client, lat=34.80, lon=-82.40, status="rejected")
        response = test_client.get("/api/events/map?status=verified")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "verified"

    def test_map_endpoint_filters_by_date_range(self, test_client):
        _insert_event(
            test_client,
            lat=34.85, lon=-82.39,
            event_date=datetime(2026, 6, 15, tzinfo=timezone.utc),
        )
        _insert_event(
            test_client,
            lat=34.80, lon=-82.40,
            event_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
        response = test_client.get(
            "/api/events/map?start_date=2026-06-01&end_date=2026-07-01"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert "2026-06" in data[0]["event_date"]

    def test_map_endpoint_radius_filter(self, test_client):
        # Greenville in range; Columbia ~100 miles away, out of range.
        _insert_event(test_client, lat=34.8526, lon=-82.394)   # Greenville
        _insert_event(test_client, lat=34.0007, lon=-81.0348)  # Columbia
        response = test_client.get(
            "/api/events/map?lat=34.8526&lon=-82.394&radius_miles=20"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_map_endpoint_invalid_radius_without_coords_returns_422(self, test_client):
        response = test_client.get("/api/events/map?radius_miles=10")
        assert response.status_code == 422

    def test_map_response_has_required_pin_fields(self, test_client):
        _insert_event(test_client, lat=34.85, lon=-82.39, business_name="Pin Cafe")
        response = test_client.get("/api/events/map")
        assert response.status_code == 200
        pin = response.json()[0]
        for field in ("id", "lat", "lon", "business_name", "status"):
            assert field in pin
