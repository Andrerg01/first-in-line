"""Integration tests for the POST /api/ingest/manual-url endpoint.

All external calls (MCP HTTP and OpenAI) are monkeypatched so no
network access or live services are required.
"""

from __future__ import annotations

import pytest

from app.schemas.ingest import LLMClaim, LLMExtractionResult
from app.services import ingest_service


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_FETCH_OK = {
    "url": "https://example.com/opening",
    "canonical_url": "https://example.com/opening",
    "domain": "example.com",
    "title": "Big Cafe Grand Opening",
    "visible_text": "Big Cafe is opening at 123 Main St, Greenville SC.",
    "http_status": 200,
    "content_type": "text/html",
    "fetch_status": "success",
    "error_message": None,
}

_NORM_OK = {
    "normalized_text": "Big Cafe is opening at 123 Main St, Greenville SC.",
    "text_hash": "integration_test_hash_abc",
}

_EXTRACTION_RELEVANT = LLMExtractionResult(
    is_relevant=True,
    business_name="Big Cafe",
    event_name="Grand Opening",
    event_type="grand_opening",
    category="cafe",
    event_date_str="2024-06-01",
    city="Greenville",
    state="SC",
    confidence_score=0.9,
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
    confidence_score=0.05,
)


def _mock_mcp_and_llm(monkeypatch, extraction=None):
    monkeypatch.setattr(
        ingest_service, "_call_mcp_fetch_page", lambda url: _FETCH_OK
    )
    monkeypatch.setattr(
        ingest_service, "_call_mcp_normalize_text", lambda text: _NORM_OK
    )
    monkeypatch.setattr(
        ingest_service,
        "_extract_event_data",
        lambda url, text: extraction or _EXTRACTION_RELEVANT,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestManualIngestEndpoint:
    def test_happy_path_returns_200(self, test_client, monkeypatch):
        _mock_mcp_and_llm(monkeypatch)
        resp = test_client.post(
            "/api/ingest/manual-url", json={"url": "https://example.com/opening"}
        )
        assert resp.status_code == 200

    def test_response_has_required_fields(self, test_client, monkeypatch):
        _mock_mcp_and_llm(monkeypatch)
        data = test_client.post(
            "/api/ingest/manual-url", json={"url": "https://example.com/opening"}
        ).json()
        assert "source_id" in data
        assert "duplicate" in data
        assert "relevant" in data
        assert "fetch_status" in data

    def test_relevant_event_created(self, test_client, monkeypatch):
        _mock_mcp_and_llm(monkeypatch)
        data = test_client.post(
            "/api/ingest/manual-url", json={"url": "https://example.com/opening"}
        ).json()
        assert data["relevant"] is True
        assert data["event_id"] is not None
        assert data["business_name"] == "Big Cafe"
        assert data["status"] == "candidate"

    def test_not_relevant_no_event(self, test_client, monkeypatch):
        _mock_mcp_and_llm(monkeypatch, extraction=_EXTRACTION_NOT_RELEVANT)
        data = test_client.post(
            "/api/ingest/manual-url", json={"url": "https://example.com/other"}
        ).json()
        assert data["relevant"] is False
        assert data["event_id"] is None

    def test_duplicate_detection(self, test_client, monkeypatch):
        _mock_mcp_and_llm(monkeypatch)
        data1 = test_client.post(
            "/api/ingest/manual-url", json={"url": "https://example.com/opening"}
        ).json()
        assert data1["duplicate"] is False

        data2 = test_client.post(
            "/api/ingest/manual-url", json={"url": "https://example.com/opening"}
        ).json()
        assert data2["duplicate"] is True
        assert data2["source_id"] == data1["source_id"]

    def test_missing_url_returns_422(self, test_client):
        resp = test_client.post("/api/ingest/manual-url", json={})
        assert resp.status_code == 422

    def test_event_visible_via_events_api(self, test_client, monkeypatch):
        """Candidate event created by ingestion appears in the events list."""
        _mock_mcp_and_llm(monkeypatch)
        ingest_data = test_client.post(
            "/api/ingest/manual-url", json={"url": "https://example.com/opening"}
        ).json()
        event_id = ingest_data["event_id"]

        event_resp = test_client.get(f"/api/events/{event_id}")
        assert event_resp.status_code == 200
        event = event_resp.json()
        assert event["business_name"] == "Big Cafe"
        assert event["status"] == "candidate"

    def test_claims_visible_via_events_api(self, test_client, monkeypatch):
        """Claims saved during ingestion are retrievable via the events API."""
        _mock_mcp_and_llm(monkeypatch)
        ingest_data = test_client.post(
            "/api/ingest/manual-url", json={"url": "https://example.com/opening"}
        ).json()
        event_id = ingest_data["event_id"]

        claims_resp = test_client.get(f"/api/events/{event_id}/claims")
        assert claims_resp.status_code == 200
        assert len(claims_resp.json()) == 1

    def test_invalid_url_scheme_returns_422(self, test_client):
        """Non-HTTP/S scheme must be rejected before any service call."""
        resp = test_client.post(
            "/api/ingest/manual-url", json={"url": "file:///etc/passwd"}
        )
        assert resp.status_code == 422

    def test_failed_fetch_returns_200_with_relevant_false(
        self, test_client, monkeypatch
    ):
        """A page that fails to fetch is persisted but not extracted."""
        monkeypatch.setattr(
            ingest_service,
            "_call_mcp_fetch_page",
            lambda url: {
                "url": url,
                "canonical_url": None,
                "domain": "example.com",
                "title": None,
                "visible_text": "",
                "http_status": None,
                "content_type": None,
                "fetch_status": "failed",
                "error_message": "Timeout",
            },
        )
        resp = test_client.post(
            "/api/ingest/manual-url", json={"url": "https://example.com/broken"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["relevant"] is False
        assert data["fetch_status"] == "failed"
        assert data["event_id"] is None
