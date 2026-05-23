"""Integration tests for the /api/events endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.models.claims import EventClaim
from app.models.events import Event
from app.models.sources import EventSource, SourceDocument


def _insert_event(client, **kwargs):
    """Directly insert an event into the test DB via the client's app state."""
    from app.db import _get_session_factory  # noqa: PLC0415

    Session = _get_session_factory()
    with Session() as db:
        defaults = dict(
            id=uuid.uuid4(),
            business_name="Integration Cafe",
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


class TestListEventsEndpoint:
    def test_empty_list(self, test_client):
        response = test_client.get("/api/events")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_inserted_event(self, test_client):
        _insert_event(test_client)
        response = test_client.get("/api/events")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["business_name"] == "Integration Cafe"

    def test_filter_by_city(self, test_client):
        _insert_event(test_client, city="Greenville")
        _insert_event(test_client, city="Columbia")
        response = test_client.get("/api/events?city=Greenville")
        assert response.status_code == 200
        assert all(e["city"] == "Greenville" for e in response.json())

    def test_filter_by_status(self, test_client):
        _insert_event(test_client, status="candidate")
        _insert_event(test_client, status="verified")
        response = test_client.get("/api/events?status=verified")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "verified"

    def test_pagination_limit(self, test_client):
        for _ in range(5):
            _insert_event(test_client)
        response = test_client.get("/api/events?limit=2")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_invalid_limit_returns_422(self, test_client):
        response = test_client.get("/api/events?limit=0")
        assert response.status_code == 422


class TestGetEventDetailEndpoint:
    def test_returns_event_detail(self, test_client):
        event_id = _insert_event(test_client)
        response = test_client.get(f"/api/events/{event_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(event_id)
        assert data["city"] == "Greenville"

    def test_returns_404_for_unknown_id(self, test_client):
        response = test_client.get(f"/api/events/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_returns_400_for_invalid_uuid(self, test_client):
        response = test_client.get("/api/events/not-a-uuid")
        assert response.status_code == 422


class TestGetEventSourcesEndpoint:
    def test_returns_empty_list_when_no_sources(self, test_client):
        event_id = _insert_event(test_client)
        response = test_client.get(f"/api/events/{event_id}/sources")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_404_for_unknown_event(self, test_client):
        response = test_client.get(f"/api/events/{uuid.uuid4()}/sources")
        assert response.status_code == 404

    def test_returns_linked_source(self, test_client):
        from app.db import _get_session_factory  # noqa: PLC0415

        event_id = _insert_event(test_client)
        Session = _get_session_factory()
        with Session() as db:
            source = SourceDocument(
                id=uuid.uuid4(),
                url="https://example.com/source",
                fetch_status="success",
            )
            db.add(source)
            db.flush()
            link = EventSource(
                id=uuid.uuid4(),
                event_id=event_id,
                source_document_id=source.id,
                relationship_type="primary_source",
            )
            db.add(link)
            db.commit()

        response = test_client.get(f"/api/events/{event_id}/sources")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["relationship_type"] == "primary_source"


class TestGetEventClaimsEndpoint:
    def test_returns_empty_list_when_no_claims(self, test_client):
        event_id = _insert_event(test_client)
        response = test_client.get(f"/api/events/{event_id}/claims")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_404_for_unknown_event(self, test_client):
        response = test_client.get(f"/api/events/{uuid.uuid4()}/claims")
        assert response.status_code == 404

    def test_returns_linked_claim(self, test_client):
        from app.db import _get_session_factory  # noqa: PLC0415

        event_id = _insert_event(test_client)
        Session = _get_session_factory()
        with Session() as db:
            source = SourceDocument(
                id=uuid.uuid4(),
                url="https://example.com/claim-source",
                fetch_status="success",
            )
            db.add(source)
            db.flush()
            claim = EventClaim(
                id=uuid.uuid4(),
                event_id=event_id,
                source_document_id=source.id,
                claim_type="business_name",
                claim_value="Integration Cafe",
            )
            db.add(claim)
            db.commit()

        response = test_client.get(f"/api/events/{event_id}/claims")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["claim_type"] == "business_name"
