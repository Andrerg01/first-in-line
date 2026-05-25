"""Integration tests for the admin geocode bulk-run endpoint."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from app.models.events import Event
from app.services import geocode_service


def _insert_event(db, *, address=None, city=None, state=None, lat=None, lon=None) -> Event:
    """Insert a minimal event directly into the DB for test setup."""
    from sqlalchemy.orm import Session
    e = Event(
        id=uuid.uuid4(),
        event_type="grand_opening",
        status="candidate",
        address=address,
        city=city,
        state=state,
        lat=lat,
        lon=lon,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _get_db_from_client(test_client):
    """Retrieve the test DB session from the client's app dependency overrides."""
    from app.db import get_db
    return next(test_client.app.dependency_overrides[get_db]())


class TestAdminGeocodeRun:
    def test_returns_counts(self, test_client):
        """POST /api/admin/geocode/run returns the expected summary keys."""
        mcp_response = {
            "lat": 34.8526, "lon": -82.3940,
            "normalized_address": "Greenville, SC",
            "confidence": 0.85, "provider": "stub", "error": None,
        }
        with patch.object(geocode_service, "_call_mcp_geocode", return_value=mcp_response):
            resp = test_client.post("/api/admin/geocode/run")

        assert resp.status_code == 200
        body = resp.json()
        # Verify all three GeocodeRunResponse fields are present and are ints
        assert isinstance(body.get("attempted"), int)
        assert isinstance(body.get("geocoded"), int)
        assert isinstance(body.get("skipped"), int)

    def test_no_events_returns_zero_counts(self, test_client):
        """Endpoint with empty DB returns all-zero counts."""
        resp = test_client.post("/api/admin/geocode/run")
        assert resp.status_code == 200
        body = resp.json()
        assert body["attempted"] == 0
        assert body["geocoded"] == 0
        assert body["skipped"] == 0

    def test_events_without_address_not_in_batch(self, test_client):
        """Events without address or city are excluded by the repository query."""
        db = _get_db_from_client(test_client)
        _insert_event(db)  # no address fields
        resp = test_client.post("/api/admin/geocode/run")
        assert resp.status_code == 200
        body = resp.json()
        # get_ungeocoded_events filters out events with no address/city
        assert body["attempted"] == 0
        assert body["geocoded"] == 0

    def test_geocodes_event_with_city(self, test_client):
        """Event with city gets geocoded when MCP succeeds."""
        db = _get_db_from_client(test_client)
        _insert_event(db, city="Greenville", state="SC")
        mcp_response = {
            "lat": 34.8526, "lon": -82.3940,
            "normalized_address": "Greenville, SC",
            "confidence": 0.85, "provider": "stub", "error": None,
        }
        with patch.object(geocode_service, "_call_mcp_geocode", return_value=mcp_response):
            resp = test_client.post("/api/admin/geocode/run")

        assert resp.status_code == 200
        assert resp.json()["geocoded"] == 1

    def test_skips_already_geocoded_events(self, test_client):
        """Events already with lat/lon are not re-processed."""
        db = _get_db_from_client(test_client)
        _insert_event(db, city="Greenville", state="SC", lat=34.85, lon=-82.39)
        resp = test_client.post("/api/admin/geocode/run")
        assert resp.status_code == 200
        body = resp.json()
        # get_ungeocoded_events filters out events with lat set → nothing attempted
        assert body["attempted"] == 0

    def test_mcp_failure_returns_partial_success(self, test_client):
        """MCP errors are non-fatal; endpoint still returns 200."""
        db = _get_db_from_client(test_client)
        _insert_event(db, city="Greenville", state="SC")
        with patch.object(
            geocode_service, "_call_mcp_geocode", side_effect=RuntimeError("MCP down")
        ):
            resp = test_client.post("/api/admin/geocode/run")

        assert resp.status_code == 200
        body = resp.json()
        assert body["geocoded"] == 0
        assert body["attempted"] == 1
