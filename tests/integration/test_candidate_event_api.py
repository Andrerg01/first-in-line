"""Integration tests for the POST /api/ingest/source-document/{id}/candidate endpoint.

Tests the worker-side candidate event creation path:
- LLM call records are persisted
- Candidate event is created
- Duplicate source document returns duplicate=True
- Irrelevant page (no claims) returns irrelevant=True
"""

from __future__ import annotations

import uuid

import pytest

from app.repositories import source_repository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_source_doc(test_client, unique_hash: str | None = None) -> dict:
    """Create a source document via the store endpoint and return the response JSON."""
    text_hash = unique_hash or str(uuid.uuid4()).replace("-", "")
    resp = test_client.post(
        "/api/ingest/source-document",
        json={
            "url": f"https://example.com/{text_hash}",
            "canonical_url": f"https://example.com/{text_hash}",
            "domain": "example.com",
            "title": "Test Page",
            "visible_text": "Some visible text about a grand opening.",
            "visible_text_hash": text_hash,
            "http_status": 200,
            "content_type": "text/html",
            "fetch_status": "success",
            "error_message": None,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _llm_call_payload(call_type: str = "classify_relevance") -> dict:
    return {
        "call_type": call_type,
        "model": "gpt-4o-mini",
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "cost_usd": 0.0000225,
        "latency_ms": 320,
        "status": "success",
        "error_message": None,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateCandidateEvent:
    def test_creates_candidate_event(self, test_client):
        """Worker extraction result creates a new candidate event and LLM call records."""
        doc = _create_source_doc(test_client)
        source_doc_id = doc["source_document_id"]

        resp = test_client.post(
            f"/api/ingest/source-document/{source_doc_id}/candidate",
            json={
                "source_document_id": source_doc_id,
                "business_name": "Burger Palace",
                "event_name": None,
                "event_type": "grand_opening",
                "category": "restaurant",
                "event_date_str": "2026-07-04",
                "address": "123 Main St",
                "city": "Greenville",
                "state": "SC",
                "promotion_text": "Free burgers!",
                "confidence_score": 0.9,
                "claims": [
                    {
                        "claim_type": "business_name",
                        "claim_value": "Burger Palace",
                        "claim_text": "Burger Palace grand opening",
                        "confidence_score": 1.0,
                    }
                ],
                "llm_calls": [
                    _llm_call_payload("classify_relevance"),
                    _llm_call_payload("classify_event_count"),
                    _llm_call_payload("extract_event"),
                ],
            },
        )

        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["created"] is True
        assert data["irrelevant"] is False
        assert data["duplicate"] is False
        assert data["event_id"] is not None
        assert len(data["llm_call_ids"]) == 3

    def test_duplicate_source_document_returns_duplicate(self, test_client):
        """Second candidate submission for the same source doc returns duplicate=True."""
        doc = _create_source_doc(test_client)
        source_doc_id = doc["source_document_id"]

        payload = {
            "source_document_id": source_doc_id,
            "business_name": "Coffee Co",
            "event_type": "grand_opening",
            "confidence_score": 0.8,
            "claims": [
                {"claim_type": "business_name", "claim_value": "Coffee Co"}
            ],
            "llm_calls": [_llm_call_payload("extract_event")],
        }

        resp1 = test_client.post(
            f"/api/ingest/source-document/{source_doc_id}/candidate", json=payload
        )
        assert resp1.status_code == 201
        assert resp1.json()["created"] is True

        resp2 = test_client.post(
            f"/api/ingest/source-document/{source_doc_id}/candidate", json=payload
        )
        assert resp2.status_code == 201
        data2 = resp2.json()
        assert data2["duplicate"] is True
        assert data2["created"] is False

    def test_irrelevant_page_no_event_created(self, test_client):
        """Submission with no business_name and no claims marks the page irrelevant."""
        doc = _create_source_doc(test_client)
        source_doc_id = doc["source_document_id"]

        resp = test_client.post(
            f"/api/ingest/source-document/{source_doc_id}/candidate",
            json={
                "source_document_id": source_doc_id,
                "business_name": None,
                "event_type": "unknown",
                "confidence_score": 0.0,
                "claims": [],
                "llm_calls": [_llm_call_payload("classify_relevance")],
            },
        )

        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["irrelevant"] is True
        assert data["created"] is False
        assert data["event_id"] is None
        # LLM call should still be recorded
        assert len(data["llm_call_ids"]) == 1

    def test_llm_calls_logged_without_event(self, test_client):
        """LLM calls are recorded even when the page is irrelevant."""
        doc = _create_source_doc(test_client)
        source_doc_id = doc["source_document_id"]

        resp = test_client.post(
            f"/api/ingest/source-document/{source_doc_id}/candidate",
            json={
                "source_document_id": source_doc_id,
                "business_name": None,
                "confidence_score": 0.0,
                "claims": [],
                "llm_calls": [
                    _llm_call_payload("classify_relevance"),
                ],
            },
        )

        assert resp.status_code == 201
        assert len(resp.json()["llm_call_ids"]) == 1

    def test_candidate_appears_in_events_list(self, test_client):
        """A newly created candidate event is returned by GET /api/events."""
        doc = _create_source_doc(test_client)
        source_doc_id = doc["source_document_id"]

        test_client.post(
            f"/api/ingest/source-document/{source_doc_id}/candidate",
            json={
                "source_document_id": source_doc_id,
                "business_name": "Visible Cafe",
                "event_type": "grand_opening",
                "category": "cafe",
                "city": "Greenville",
                "state": "SC",
                "confidence_score": 0.85,
                "claims": [],
                "llm_calls": [],
            },
        )

        events_resp = test_client.get("/api/events")
        assert events_resp.status_code == 200
        events = events_resp.json()
        names = [e["business_name"] for e in events]
        assert "Visible Cafe" in names

    def test_candidate_in_review_queue(self, test_client):
        """A candidate event created by the worker appears in the admin review queue."""
        doc = _create_source_doc(test_client)
        source_doc_id = doc["source_document_id"]

        test_client.post(
            f"/api/ingest/source-document/{source_doc_id}/candidate",
            json={
                "source_document_id": source_doc_id,
                "business_name": "Queue Burgers",
                "event_type": "grand_opening",
                "category": "restaurant",
                "city": "Greenville",
                "state": "SC",
                "confidence_score": 0.88,
                "claims": [],
                "llm_calls": [],
            },
        )

        queue_resp = test_client.get("/api/admin/review-queue")
        assert queue_resp.status_code == 200
        queue = queue_resp.json()
        names = [e["business_name"] for e in queue]
        assert "Queue Burgers" in names


class TestCandidateEventUnknownSourceDoc:
    """Submitting to an unknown source_document_id must return 404."""

    def test_unknown_source_doc_returns_404(self, test_client):
        """POST to a non-existent source document should return HTTP 404."""
        import uuid

        unknown_id = str(uuid.uuid4())
        resp = test_client.post(
            f"/api/ingest/source-document/{unknown_id}/candidate",
            json={
                "business_name": "Ghost Cafe",
                "event_type": "grand_opening",
                "claims": [],
                "llm_calls": [],
            },
        )
        assert resp.status_code == 404
