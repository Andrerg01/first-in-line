"""Unit tests for the ingest service layer.

All MCP HTTP calls and OpenAI calls are monkeypatched so these tests
run without any network access or live services.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.models.events import Event
from app.models.processing import ProcessingDecision
from app.models.sources import EventSource, SourceDocument
from app.schemas.ingest import LLMClaim, LLMExtractionResult, ManualIngestResponse
from app.services import ingest_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FETCH_OK = {
    "url": "https://example.com/opening",
    "canonical_url": "https://example.com/opening",
    "domain": "example.com",
    "title": "Big Cafe Grand Opening",
    "visible_text": "Big Cafe is opening at 123 Main St, Greenville SC on June 1!",
    "http_status": 200,
    "content_type": "text/html",
    "fetch_status": "success",
    "error_message": None,
}

_NORM_OK = {
    "normalized_text": "Big Cafe is opening at 123 Main St, Greenville SC on June 1!",
    "text_hash": "abc123hash",
}

_EXTRACTION_RELEVANT = LLMExtractionResult(
    is_relevant=True,
    business_name="Big Cafe",
    event_name="Grand Opening",
    event_type="grand_opening",
    category="cafe",
    event_date_str="2024-06-01",
    address="123 Main St",
    city="Greenville",
    state="SC",
    promotion_text="Join us!",
    confidence_score=0.92,
    claims=[
        LLMClaim(
            claim_type="business_name",
            claim_value="Big Cafe",
            claim_text="Big Cafe is opening",
        )
    ],
)

_EXTRACTION_NOT_RELEVANT = LLMExtractionResult(
    is_relevant=False,
    confidence_score=0.1,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_mcp_and_llm(monkeypatch, fetch=None, norm=None, extraction=None):
    """Patch the three external calls used by ingest_manual_url."""
    monkeypatch.setattr(
        ingest_service, "_call_mcp_fetch_page", lambda url: fetch or _FETCH_OK
    )
    monkeypatch.setattr(
        ingest_service, "_call_mcp_normalize_text", lambda text: norm or _NORM_OK
    )
    monkeypatch.setattr(
        ingest_service,
        "_extract_event_data",
        lambda url, text: extraction or _EXTRACTION_RELEVANT,
    )


# ---------------------------------------------------------------------------
# Tests — happy path (relevant event created)
# ---------------------------------------------------------------------------


class TestIngestManualUrlRelevant:
    def test_returns_ingest_response(self, db_session, monkeypatch):
        _patch_mcp_and_llm(monkeypatch)
        resp = ingest_service.ingest_manual_url(db_session, "https://example.com/opening")
        assert isinstance(resp, ManualIngestResponse)

    def test_relevant_flag_true(self, db_session, monkeypatch):
        _patch_mcp_and_llm(monkeypatch)
        resp = ingest_service.ingest_manual_url(db_session, "https://example.com/opening")
        assert resp.relevant is True

    def test_duplicate_flag_false_on_first_run(self, db_session, monkeypatch):
        _patch_mcp_and_llm(monkeypatch)
        resp = ingest_service.ingest_manual_url(db_session, "https://example.com/opening")
        assert resp.duplicate is False

    def test_event_id_present(self, db_session, monkeypatch):
        _patch_mcp_and_llm(monkeypatch)
        resp = ingest_service.ingest_manual_url(db_session, "https://example.com/opening")
        assert resp.event_id is not None

    def test_event_fields_populated(self, db_session, monkeypatch):
        _patch_mcp_and_llm(monkeypatch)
        resp = ingest_service.ingest_manual_url(db_session, "https://example.com/opening")
        assert resp.business_name == "Big Cafe"
        assert resp.category == "cafe"
        assert resp.city == "Greenville"
        assert resp.state == "SC"
        assert resp.status == "candidate"

    def test_claims_count(self, db_session, monkeypatch):
        _patch_mcp_and_llm(monkeypatch)
        resp = ingest_service.ingest_manual_url(db_session, "https://example.com/opening")
        assert resp.claims_count == 1

    def test_event_persisted_to_db(self, db_session, monkeypatch):
        _patch_mcp_and_llm(monkeypatch)
        resp = ingest_service.ingest_manual_url(db_session, "https://example.com/opening")
        event = db_session.get(Event, resp.event_id)
        assert event is not None
        assert event.business_name == "Big Cafe"
        assert event.status == "candidate"

    def test_source_document_persisted(self, db_session, monkeypatch):
        _patch_mcp_and_llm(monkeypatch)
        resp = ingest_service.ingest_manual_url(db_session, "https://example.com/opening")
        doc = db_session.get(SourceDocument, resp.source_id)
        assert doc is not None
        assert doc.visible_text_hash == "abc123hash"

    def test_processing_decision_created(self, db_session, monkeypatch):
        from sqlalchemy import select

        _patch_mcp_and_llm(monkeypatch)
        resp = ingest_service.ingest_manual_url(db_session, "https://example.com/opening")
        decision = db_session.scalars(
            select(ProcessingDecision).where(
                ProcessingDecision.source_document_id == resp.source_id
            )
        ).first()
        assert decision is not None
        assert decision.decision_type == "manual_ingest"
        assert decision.decision_value == "candidate_created"


# ---------------------------------------------------------------------------
# Tests — not relevant (event not created)
# ---------------------------------------------------------------------------


class TestIngestManualUrlNotRelevant:
    def test_relevant_flag_false(self, db_session, monkeypatch):
        _patch_mcp_and_llm(monkeypatch, extraction=_EXTRACTION_NOT_RELEVANT)
        resp = ingest_service.ingest_manual_url(db_session, "https://example.com/other")
        assert resp.relevant is False

    def test_event_id_none_when_not_relevant(self, db_session, monkeypatch):
        _patch_mcp_and_llm(monkeypatch, extraction=_EXTRACTION_NOT_RELEVANT)
        resp = ingest_service.ingest_manual_url(db_session, "https://example.com/other")
        assert resp.event_id is None

    def test_source_document_still_created(self, db_session, monkeypatch):
        _patch_mcp_and_llm(monkeypatch, extraction=_EXTRACTION_NOT_RELEVANT)
        resp = ingest_service.ingest_manual_url(db_session, "https://example.com/other")
        doc = db_session.get(SourceDocument, resp.source_id)
        assert doc is not None

    def test_processing_decision_not_relevant(self, db_session, monkeypatch):
        from sqlalchemy import select

        _patch_mcp_and_llm(monkeypatch, extraction=_EXTRACTION_NOT_RELEVANT)
        resp = ingest_service.ingest_manual_url(db_session, "https://example.com/other")
        decision = db_session.scalars(
            select(ProcessingDecision).where(
                ProcessingDecision.source_document_id == resp.source_id
            )
        ).first()
        assert decision is not None
        assert decision.decision_value == "not_relevant"


# ---------------------------------------------------------------------------
# Tests — duplicate detection
# ---------------------------------------------------------------------------


class TestIngestManualUrlDuplicate:
    def test_duplicate_returns_early(self, db_session, monkeypatch):
        """Second call with same hash returns duplicate=True without creating a new event."""
        _patch_mcp_and_llm(monkeypatch)
        resp1 = ingest_service.ingest_manual_url(db_session, "https://example.com/opening")
        assert resp1.duplicate is False

        # Second call with same hash should deduplicate
        resp2 = ingest_service.ingest_manual_url(db_session, "https://example.com/opening")
        assert resp2.duplicate is True
        assert resp2.fetch_status == "skipped"
        assert resp2.source_id == resp1.source_id

    def test_duplicate_points_to_existing_event(self, db_session, monkeypatch):
        _patch_mcp_and_llm(monkeypatch)
        resp1 = ingest_service.ingest_manual_url(db_session, "https://example.com/opening")
        resp2 = ingest_service.ingest_manual_url(db_session, "https://example.com/opening")
        assert resp2.event_id == resp1.event_id


# ---------------------------------------------------------------------------
# Tests — date parsing helper
# ---------------------------------------------------------------------------


class TestParseEventDate:
    def test_valid_date(self):
        result = ingest_service._parse_event_date("2024-06-01")
        assert result == datetime(2024, 6, 1, tzinfo=timezone.utc)

    def test_none_returns_none(self):
        assert ingest_service._parse_event_date(None) is None

    def test_invalid_string_returns_none(self):
        assert ingest_service._parse_event_date("not-a-date") is None
