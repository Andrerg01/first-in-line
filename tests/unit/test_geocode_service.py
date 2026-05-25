"""Unit tests for the geocode service."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.models.events import Event
from app.services import geocode_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event(db, *, address=None, city=None, state=None, lat=None, lon=None) -> Event:
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
    db.flush()
    return e


# ---------------------------------------------------------------------------
# _build_address_query
# ---------------------------------------------------------------------------


class TestBuildAddressQuery:
    def test_full_address_returns_all_parts(self):
        class FakeEvent:
            address = "123 Main St"
            city = "Greenville"
            state = "SC"

        result = geocode_service._build_address_query(FakeEvent())  # type: ignore[arg-type]
        assert result == "123 Main St, Greenville, SC"

    def test_city_only_returns_city_state(self):
        class FakeEvent:
            address = None
            city = "Greenville"
            state = "SC"

        result = geocode_service._build_address_query(FakeEvent())  # type: ignore[arg-type]
        assert result == "Greenville, SC"

    def test_no_fields_returns_none(self):
        class FakeEvent:
            address = None
            city = None
            state = None

        result = geocode_service._build_address_query(FakeEvent())  # type: ignore[arg-type]
        assert result is None

    def test_address_without_city_still_returned(self):
        class FakeEvent:
            address = "456 Oak Ave"
            city = None
            state = None

        result = geocode_service._build_address_query(FakeEvent())  # type: ignore[arg-type]
        assert result == "456 Oak Ave"


# ---------------------------------------------------------------------------
# geocode_event — skip conditions
# ---------------------------------------------------------------------------


class TestGeocodeEventSkips:
    def test_already_geocoded_returns_false(self, db_session):
        event = _event(db_session, city="Greenville", state="SC", lat=34.85, lon=-82.39)
        result = geocode_service.geocode_event(db_session, event)
        assert result is False

    def test_no_address_fields_returns_false(self, db_session):
        event = _event(db_session)
        result = geocode_service.geocode_event(db_session, event)
        assert result is False


# ---------------------------------------------------------------------------
# _call_mcp_geocode — URL, body, and raise_for_status contract
# ---------------------------------------------------------------------------


class TestCallMcpGeocodeContract:
    def test_posts_to_correct_endpoint_with_correct_body(self):
        """Verify _call_mcp_geocode sends the right URL and JSON body."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "lat": 34.85, "lon": -82.39,
            "normalized_address": "Greenville, SC",
            "confidence": 0.85, "provider": "stub", "error": None,
        }

        with patch("httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_ctx
            mock_ctx.post.return_value = mock_response

            result = geocode_service._call_mcp_geocode("123 Main St, Greenville, SC")

        call_args = mock_ctx.post.call_args
        assert "/tools/geo.geocode_address" in call_args[0][0]
        assert call_args[1]["json"] == {"address": "123 Main St, Greenville, SC"}
        mock_response.raise_for_status.assert_called_once()
        assert result["lat"] == 34.85

    def test_propagates_http_error(self):
        """raise_for_status on a 5xx response propagates to the caller."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Server Error", request=MagicMock(), response=MagicMock()
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_ctx
            mock_ctx.post.return_value = mock_response

            with pytest.raises(httpx.HTTPStatusError):
                geocode_service._call_mcp_geocode("any address")


# ---------------------------------------------------------------------------
# geocode_event — MCP call mocking
# ---------------------------------------------------------------------------


class TestGeocodeEventMCP:
    def test_successful_geocode_updates_event(self, db_session):
        event = _event(db_session, address="123 Main St", city="Greenville", state="SC")
        mcp_response = {
            "lat": 34.8526,
            "lon": -82.3940,
            "normalized_address": "Greenville, SC",
            "confidence": 0.85,
            "provider": "stub",
            "error": None,
        }
        with patch.object(geocode_service, "_call_mcp_geocode", return_value=mcp_response):
            result = geocode_service.geocode_event(db_session, event)

        assert result is True
        assert float(event.lat) == pytest.approx(34.8526, abs=1e-4)
        assert float(event.lon) == pytest.approx(-82.3940, abs=1e-4)

    def test_no_result_returns_false(self, db_session):
        event = _event(db_session, city="Nowhere", state="ZZ")
        mcp_response = {
            "lat": None,
            "lon": None,
            "normalized_address": None,
            "confidence": None,
            "provider": "stub",
            "error": "No results found",
        }
        with patch.object(geocode_service, "_call_mcp_geocode", return_value=mcp_response):
            result = geocode_service.geocode_event(db_session, event)

        assert result is False
        assert event.lat is None

    def test_mcp_exception_returns_false(self, db_session):
        event = _event(db_session, city="Greenville", state="SC")
        with patch.object(geocode_service, "_call_mcp_geocode", side_effect=RuntimeError("MCP down")):
            result = geocode_service.geocode_event(db_session, event)

        assert result is False
        assert event.lat is None


# ---------------------------------------------------------------------------
# geocode_ungeocoded_events
# ---------------------------------------------------------------------------


class TestGeocodeUngeocoodedEvents:
    def test_no_address_events_not_in_batch(self, db_session):
        """Events without address or city are excluded by the repository query."""
        _event(db_session)  # no address, city, or state
        result = geocode_service.geocode_ungeocoded_events(db_session)
        # get_ungeocoded_events filters out events with no address/city,
        # so they are never attempted or skipped.
        assert result["attempted"] == 0
        assert result["geocoded"] == 0
        assert result["skipped"] == 0

    def test_geocodes_events_with_address(self, db_session):
        _event(db_session, city="Greenville", state="SC")
        mcp_response = {
            "lat": 34.8526,
            "lon": -82.3940,
            "normalized_address": "Greenville, SC",
            "confidence": 0.85,
            "provider": "stub",
            "error": None,
        }
        with patch.object(geocode_service, "_call_mcp_geocode", return_value=mcp_response):
            result = geocode_service.geocode_ungeocoded_events(db_session)

        assert result["geocoded"] == 1
        assert result["skipped"] == 0

    def test_skips_already_geocoded(self, db_session):
        _event(db_session, city="Greenville", state="SC", lat=34.85, lon=-82.39)
        result = geocode_service.geocode_ungeocoded_events(db_session)
        # already geocoded → not returned by get_ungeocoded_events
        assert result["attempted"] == 0
