"""Integration tests for the admin review queue endpoint."""
from __future__ import annotations

import uuid

import pytest

from app.models.events import Event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_event(db, status: str = "candidate", business_name: str = "Test Biz") -> Event:
    """Insert a minimal event directly into the test DB."""
    from datetime import datetime, timezone

    event = Event(
        business_name=business_name,
        event_type="grand_opening",
        status=status,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


# ---------------------------------------------------------------------------
# Review queue tests
# ---------------------------------------------------------------------------


class TestReviewQueue:
    """GET /api/admin/review-queue."""

    def test_empty_queue_returns_empty_list(self, test_client):
        resp = test_client.get("/api/admin/review-queue")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_candidate_events_appear_in_queue(self, test_client):
        from fastapi.testclient import TestClient
        from app.db import get_db

        # Use the override DB session directly to insert data.
        db = next(test_client.app.dependency_overrides[get_db]())
        _create_event(db, status="candidate", business_name="New Bistro")

        resp = test_client.get("/api/admin/review-queue")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["business_name"] == "New Bistro"
        assert data[0]["status"] == "candidate"

    def test_needs_review_events_appear_in_queue(self, test_client):
        from app.db import get_db

        db = next(test_client.app.dependency_overrides[get_db]())
        _create_event(db, status="needs_review", business_name="Review Me")

        resp = test_client.get("/api/admin/review-queue")
        assert resp.status_code == 200
        statuses = [e["status"] for e in resp.json()]
        assert "needs_review" in statuses

    def test_verified_events_not_in_queue(self, test_client):
        from app.db import get_db

        db = next(test_client.app.dependency_overrides[get_db]())
        _create_event(db, status="verified", business_name="Already Verified")

        resp = test_client.get("/api/admin/review-queue")
        assert resp.status_code == 200
        names = [e["business_name"] for e in resp.json()]
        assert "Already Verified" not in names

    def test_limit_parameter_respected(self, test_client):
        from app.db import get_db

        db = next(test_client.app.dependency_overrides[get_db]())
        for i in range(5):
            _create_event(db, status="candidate", business_name=f"Biz {i}")

        resp = test_client.get("/api/admin/review-queue?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) <= 2


# ---------------------------------------------------------------------------
# Search run endpoint tests
# ---------------------------------------------------------------------------


class TestSearchRunEndpoints:
    """POST /api/ingest/search-run and PATCH /api/ingest/search-run/{id}."""

    def test_create_search_run_returns_201(self, test_client):
        resp = test_client.post(
            "/api/ingest/search-run",
            json={"run_type": "scheduled_daily", "query_set_version": "v1"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["run_type"] == "scheduled_daily"
        assert data["status"] == "running"
        assert "id" in data

    def test_update_search_run_status_to_completed(self, test_client):
        create_resp = test_client.post(
            "/api/ingest/search-run",
            json={"run_type": "scheduled_daily"},
        )
        run_id = create_resp.json()["id"]

        patch_resp = test_client.patch(
            f"/api/ingest/search-run/{run_id}",
            json={"status": "completed"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["status"] == "completed"

    def test_update_nonexistent_run_returns_404(self, test_client):
        resp = test_client.patch(
            f"/api/ingest/search-run/{uuid.uuid4()}",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    def test_add_search_results_to_run(self, test_client):
        create_resp = test_client.post(
            "/api/ingest/search-run",
            json={"run_type": "scheduled_daily"},
        )
        run_id = create_resp.json()["id"]

        results_resp = test_client.post(
            f"/api/ingest/search-run/{run_id}/results",
            json={
                "results": [
                    {
                        "query": "grand opening Greenville SC",
                        "rank": 1,
                        "title": "New Restaurant Opens",
                        "url": "https://example.com/news/restaurant",
                        "snippet": "A new restaurant is opening soon.",
                        "search_provider": "duckduckgo",
                    }
                ]
            },
        )
        assert results_resp.status_code == 201
        assert results_resp.json()["saved"] == 1

    def test_add_results_to_nonexistent_run_returns_404(self, test_client):
        resp = test_client.post(
            f"/api/ingest/search-run/{uuid.uuid4()}/results",
            json={"results": [{"url": "https://example.com"}]},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Source document store endpoint tests
# ---------------------------------------------------------------------------


class TestSourceDocumentEndpoint:
    """POST /api/ingest/source-document."""

    def _payload(self, url: str = "https://example.com/page", text_hash: str = "abc123") -> dict:
        return {
            "url": url,
            "canonical_url": url,
            "domain": "example.com",
            "title": "Test Page",
            "visible_text": "Some visible text",
            "visible_text_hash": text_hash,
            "http_status": 200,
            "content_type": "text/html",
            "fetch_status": "success",
            "error_message": None,
        }

    def test_new_document_returns_created_true(self, test_client):
        resp = test_client.post("/api/ingest/source-document", json=self._payload())
        assert resp.status_code == 201
        data = resp.json()
        assert data["created"] is True
        assert data["duplicate"] is False
        assert "source_document_id" in data

    def test_duplicate_document_returns_created_false(self, test_client):
        payload = self._payload()
        resp1 = test_client.post("/api/ingest/source-document", json=payload)
        assert resp1.status_code == 201

        resp2 = test_client.post("/api/ingest/source-document", json=payload)
        assert resp2.status_code == 201
        data = resp2.json()
        assert data["created"] is False
        assert data["duplicate"] is True
        # IDs should match
        assert data["source_document_id"] == resp1.json()["source_document_id"]

    def test_different_hashes_create_separate_documents(self, test_client):
        resp1 = test_client.post(
            "/api/ingest/source-document",
            json=self._payload(url="https://example.com/a", text_hash="hash_a"),
        )
        resp2 = test_client.post(
            "/api/ingest/source-document",
            json=self._payload(url="https://example.com/b", text_hash="hash_b"),
        )
        assert resp1.json()["source_document_id"] != resp2.json()["source_document_id"]
        assert resp1.json()["created"] is True
        assert resp2.json()["created"] is True
