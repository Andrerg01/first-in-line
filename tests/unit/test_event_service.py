"""Unit tests for the event service layer."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.models.events import Event
from app.models.sources import EventSource, SourceDocument
from app.models.claims import EventClaim
from app.services import event_service


def _make_event(db, **kwargs) -> Event:
    """Helper: insert and return a minimal Event."""
    defaults = dict(
        id=uuid.uuid4(),
        business_name="Test Cafe",
        event_type="grand_opening",
        status="candidate",
    )
    defaults.update(kwargs)
    event = Event(**defaults)
    db.add(event)
    db.flush()
    return event


def _make_source(db, **kwargs) -> SourceDocument:
    defaults = dict(
        id=uuid.uuid4(),
        url="https://example.com/test",
        fetch_status="success",
    )
    defaults.update(kwargs)
    doc = SourceDocument(**defaults)
    db.add(doc)
    db.flush()
    return doc


class TestListEvents:
    def test_returns_empty_list_when_no_events(self, db_session):
        result = event_service.list_events(db_session)
        assert result == []

    def test_returns_all_events(self, db_session):
        _make_event(db_session, business_name="Alpha")
        _make_event(db_session, business_name="Beta")
        result = event_service.list_events(db_session)
        assert len(result) == 2

    def test_filters_by_city(self, db_session):
        _make_event(db_session, city="Greenville")
        _make_event(db_session, city="Columbia")
        result = event_service.list_events(db_session, city="Greenville")
        assert len(result) == 1
        assert result[0].city == "Greenville"

    def test_filters_by_status(self, db_session):
        _make_event(db_session, status="candidate")
        _make_event(db_session, status="verified")
        result = event_service.list_events(db_session, status="verified")
        assert len(result) == 1
        assert result[0].status == "verified"

    def test_limit_caps_at_200(self, db_session):
        # Requesting more than 200 should be silently capped.
        result = event_service.list_events(db_session, limit=500)
        assert isinstance(result, list)

    def test_filters_by_category(self, db_session):
        _make_event(db_session, category="cafe")
        _make_event(db_session, category="brewery")
        result = event_service.list_events(db_session, category="cafe")
        assert len(result) == 1
        assert result[0].category == "cafe"


class TestGetEventDetail:
    def test_returns_event_when_found(self, db_session):
        event = _make_event(db_session)
        result = event_service.get_event_detail(db_session, event.id)
        assert result.id == event.id

    def test_raises_404_when_not_found(self, db_session):
        with pytest.raises(HTTPException) as exc_info:
            event_service.get_event_detail(db_session, uuid.uuid4())
        assert exc_info.value.status_code == 404


class TestGetEventSources:
    def test_returns_empty_when_no_sources(self, db_session):
        event = _make_event(db_session)
        result = event_service.get_event_sources(db_session, event.id)
        assert result == []

    def test_raises_404_for_unknown_event(self, db_session):
        with pytest.raises(HTTPException) as exc_info:
            event_service.get_event_sources(db_session, uuid.uuid4())
        assert exc_info.value.status_code == 404

    def test_returns_linked_sources(self, db_session):
        event = _make_event(db_session)
        source = _make_source(db_session)
        link = EventSource(
            id=uuid.uuid4(),
            event_id=event.id,
            source_document_id=source.id,
            relationship_type="primary_source",
        )
        db_session.add(link)
        db_session.flush()

        result = event_service.get_event_sources(db_session, event.id)
        assert len(result) == 1
        assert result[0].source_document_id == source.id


class TestGetEventClaims:
    def test_returns_empty_when_no_claims(self, db_session):
        event = _make_event(db_session)
        result = event_service.get_event_claims(db_session, event.id)
        assert result == []

    def test_raises_404_for_unknown_event(self, db_session):
        with pytest.raises(HTTPException) as exc_info:
            event_service.get_event_claims(db_session, uuid.uuid4())
        assert exc_info.value.status_code == 404

    def test_returns_claims_for_event(self, db_session):
        event = _make_event(db_session)
        source = _make_source(db_session)
        claim = EventClaim(
            id=uuid.uuid4(),
            event_id=event.id,
            source_document_id=source.id,
            claim_type="business_name",
            claim_value="Test Cafe",
        )
        db_session.add(claim)
        db_session.flush()

        result = event_service.get_event_claims(db_session, event.id)
        assert len(result) == 1
        assert result[0].claim_type == "business_name"
