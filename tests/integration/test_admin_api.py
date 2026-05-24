"""Integration tests for the admin review queue endpoint."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.events import Event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_event(
    db,
    status: str = "candidate",
    business_name: str = "Test Biz",
    **kwargs,
) -> Event:
    """Insert a minimal event directly into the test DB."""
    event = Event(
        business_name=business_name,
        event_type="grand_opening",
        status=status,
        **kwargs,
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

    def test_offset_applies_to_global_mixed_status_order(self, test_client):
        from app.db import get_db

        db = next(test_client.app.dependency_overrides[get_db]())
        base = datetime.now(timezone.utc)
        newest = _create_event(
            db,
            status="needs_review",
            business_name="Newest Review",
            created_at=base,
        )
        middle = _create_event(
            db,
            status="candidate",
            business_name="Middle Candidate",
            created_at=base - timedelta(minutes=1),
        )
        _oldest = _create_event(
            db,
            status="needs_review",
            business_name="Oldest Review",
            created_at=base - timedelta(minutes=2),
        )

        resp = test_client.get("/api/admin/review-queue?limit=1&offset=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == str(middle.id)

    def test_same_timestamp_rows_page_without_overlap(self, test_client):
        from app.db import get_db

        db = next(test_client.app.dependency_overrides[get_db]())
        stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for index in range(3):
            _create_event(
                db,
                status="candidate",
                business_name=f"Same Stamp {index}",
                created_at=stamp,
            )

        page1 = test_client.get("/api/admin/review-queue?limit=2&offset=0")
        page2 = test_client.get("/api/admin/review-queue?limit=2&offset=2")
        assert page1.status_code == 200
        assert page2.status_code == 200
        ids1 = {row["id"] for row in page1.json()}
        ids2 = {row["id"] for row in page2.json()}
        assert ids1.isdisjoint(ids2)


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


# ---------------------------------------------------------------------------
# Dedup admin endpoints tests
# ---------------------------------------------------------------------------


class TestAdminDedupEndpoints:
    """Integration tests for conflict, duplicate flag, and merge endpoints."""

    def test_flag_duplicate_sets_fields(self, test_client):
        from app.db import get_db

        db = next(test_client.app.dependency_overrides[get_db]())
        source = _create_event(db, status="candidate", business_name="Source")
        target = _create_event(db, status="verified", business_name="Target")

        resp = test_client.post(
            f"/api/admin/events/{source.id}/flag-duplicate",
            json={"duplicate_of_id": str(target.id)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["possible_duplicate"] is True
        assert data["duplicate_of_id"] == str(target.id)

    def test_flag_duplicate_clear_unsets_fields(self, test_client):
        from app.db import get_db

        db = next(test_client.app.dependency_overrides[get_db]())
        source = _create_event(db, status="candidate", business_name="Source")
        target = _create_event(db, status="verified", business_name="Target")

        set_resp = test_client.post(
            f"/api/admin/events/{source.id}/flag-duplicate",
            json={"duplicate_of_id": str(target.id)},
        )
        assert set_resp.status_code == 200

        clear_resp = test_client.post(
            f"/api/admin/events/{source.id}/flag-duplicate",
            json={"duplicate_of_id": None},
        )
        assert clear_resp.status_code == 200
        data = clear_resp.json()
        assert data["possible_duplicate"] is False
        assert data["duplicate_of_id"] is None

    def test_flag_duplicate_same_event_id_returns_422(self, test_client):
        from app.db import get_db

        db = next(test_client.app.dependency_overrides[get_db]())
        event = _create_event(db, status="candidate", business_name="Same")

        resp = test_client.post(
            f"/api/admin/events/{event.id}/flag-duplicate",
            json={"duplicate_of_id": str(event.id)},
        )
        assert resp.status_code == 422

    def test_flag_duplicate_non_root_target_returns_422(self, test_client):
        from app.db import get_db

        db = next(test_client.app.dependency_overrides[get_db]())
        canonical = _create_event(db, status="verified", business_name="Canonical")
        non_root_target = _create_event(
            db,
            status="candidate",
            business_name="Non Root",
            possible_duplicate=True,
            duplicate_of_id=canonical.id,
        )
        source = _create_event(db, status="candidate", business_name="Source")

        resp = test_client.post(
            f"/api/admin/events/{source.id}/flag-duplicate",
            json={"duplicate_of_id": str(non_root_target.id)},
        )
        assert resp.status_code == 422

    def test_conflicts_endpoint_returns_claim_differences(self, test_client):
        from app.db import get_db
        from app.models.claims import EventClaim
        from app.models.sources import SourceDocument

        db = next(test_client.app.dependency_overrides[get_db]())
        a = _create_event(db, status="candidate", business_name="Alpha")
        b = _create_event(db, status="verified", business_name="Beta")

        source_doc = SourceDocument(
            id=uuid.uuid4(),
            url="https://example.com/conflict",
            fetch_status="success",
        )
        db.add(source_doc)
        db.flush()

        db.add(
            EventClaim(
                id=uuid.uuid4(),
                event_id=a.id,
                source_document_id=source_doc.id,
                claim_type="event_date",
                claim_value="2026-06-01",
            )
        )
        db.add(
            EventClaim(
                id=uuid.uuid4(),
                event_id=b.id,
                source_document_id=source_doc.id,
                claim_type="event_date",
                claim_value="2026-07-01",
            )
        )
        db.commit()

        resp = test_client.get(
            f"/api/admin/events/{a.id}/conflicts?other_id={b.id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "event_date" in data["conflicting_claim_types"]
        assert data["event_a"]["id"] == str(a.id)
        assert data["event_b"]["id"] == str(b.id)

    def test_merge_endpoint_marks_source_and_keeps_target(self, test_client):
        from app.db import get_db
        from app.models.sources import SourceDocument, EventSource

        db = next(test_client.app.dependency_overrides[get_db]())
        source = _create_event(db, status="candidate", business_name="Source Name")
        target = _create_event(db, status="verified", business_name="Target Name")

        source_doc = SourceDocument(
            id=uuid.uuid4(),
            url="https://example.com/source",
            fetch_status="success",
        )
        target_doc = SourceDocument(
            id=uuid.uuid4(),
            url="https://example.com/target",
            fetch_status="success",
        )
        db.add(source_doc)
        db.add(target_doc)
        db.flush()
        db.add(EventSource(event_id=source.id, source_document_id=source_doc.id))
        db.add(EventSource(event_id=target.id, source_document_id=target_doc.id))
        db.commit()

        resp = test_client.post(
            f"/api/admin/events/{source.id}/merge",
            json={
                "target_id": str(target.id),
                "canonical_fields": {"business_name": "Canonical Name"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(target.id)
        assert data["business_name"] == "Canonical Name"

        # Confirm source got merged state via existing event detail endpoint
        source_after = test_client.get(f"/api/events/{source.id}")
        assert source_after.status_code == 200
        assert source_after.json()["status"] == "merged"

        target_sources = test_client.get(f"/api/events/{target.id}/sources")
        assert target_sources.status_code == 200
        urls = {row["source_document"]["url"] for row in target_sources.json()}
        assert urls == {"https://example.com/source", "https://example.com/target"}

    def test_merge_endpoint_dedupes_shared_source_links(self, test_client):
        from app.db import get_db
        from app.models.sources import EventSource, SourceDocument

        db = next(test_client.app.dependency_overrides[get_db]())
        source = _create_event(db, status="candidate", business_name="Source Name")
        target = _create_event(db, status="verified", business_name="Target Name")

        shared_doc = SourceDocument(
            id=uuid.uuid4(),
            url="https://example.com/shared",
            fetch_status="success",
        )
        db.add(shared_doc)
        db.flush()
        db.add(EventSource(event_id=source.id, source_document_id=shared_doc.id))
        db.add(EventSource(event_id=target.id, source_document_id=shared_doc.id))
        db.commit()

        resp = test_client.post(
            f"/api/admin/events/{source.id}/merge",
            json={"target_id": str(target.id), "canonical_fields": {}},
        )
        assert resp.status_code == 200

        target_sources = test_client.get(f"/api/events/{target.id}/sources")
        assert target_sources.status_code == 200
        urls = [row["source_document"]["url"] for row in target_sources.json()]
        assert urls == ["https://example.com/shared"]

    def test_merge_clears_possible_duplicate_on_source(self, test_client):
        from app.db import get_db

        db = next(test_client.app.dependency_overrides[get_db]())
        source = _create_event(db, status="candidate", business_name="Source Name")
        target = _create_event(db, status="verified", business_name="Target Name")

        flag_resp = test_client.post(
            f"/api/admin/events/{source.id}/flag-duplicate",
            json={"duplicate_of_id": str(target.id)},
        )
        assert flag_resp.status_code == 200

        merge_resp = test_client.post(
            f"/api/admin/events/{source.id}/merge",
            json={"target_id": str(target.id), "canonical_fields": {}},
        )
        assert merge_resp.status_code == 200

        source_after = test_client.get(f"/api/events/{source.id}")
        assert source_after.status_code == 200
        assert source_after.json()["possible_duplicate"] is False

    def test_merge_repoints_duplicate_children_to_target(self, test_client):
        from app.db import get_db

        db = next(test_client.app.dependency_overrides[get_db]())
        target = _create_event(db, status="verified", business_name="Target Name")
        source = _create_event(
            db,
            status="candidate",
            business_name="Source Name",
            possible_duplicate=True,
            duplicate_of_id=target.id,
        )
        child = _create_event(
            db,
            status="candidate",
            business_name="Child Name",
            possible_duplicate=True,
            duplicate_of_id=source.id,
        )

        merge_resp = test_client.post(
            f"/api/admin/events/{source.id}/merge",
            json={"target_id": str(target.id), "canonical_fields": {}},
        )
        assert merge_resp.status_code == 200

        child_after = test_client.get(f"/api/events/{child.id}")
        assert child_after.status_code == 200
        assert child_after.json()["possible_duplicate"] is True
        assert child_after.json()["duplicate_of_id"] == str(target.id)

    def test_merge_endpoint_non_root_target_422(self, test_client):
        from app.db import get_db

        db = next(test_client.app.dependency_overrides[get_db]())
        canonical = _create_event(db, status="verified", business_name="Canonical")
        non_root_target = _create_event(
            db,
            status="candidate",
            business_name="Non Root",
            possible_duplicate=True,
            duplicate_of_id=canonical.id,
        )
        source = _create_event(db, status="candidate", business_name="Source")

        resp = test_client.post(
            f"/api/admin/events/{source.id}/merge",
            json={"target_id": str(non_root_target.id), "canonical_fields": {}},
        )
        assert resp.status_code == 422

    def test_retroactive_dedup_flags_existing_duplicates(self, test_client):
        from app.db import get_db

        db = next(test_client.app.dependency_overrides[get_db]())
        older = _create_event(
            db,
            status="verified",
            business_name="Enlo Restaurant",
            city="Greenville",
            state="SC",
            address="123 Main St",
            event_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        newer = _create_event(
            db,
            status="candidate",
            business_name="Enlo",
            city="Greenville",
            state="SC",
            address="123 Main Street",
            event_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )

        resp = test_client.post("/api/admin/dedup/retroactive-run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scanned"] >= 2
        assert data["flagged"] >= 1

        newer_after = test_client.get(f"/api/events/{newer.id}")
        assert newer_after.status_code == 200
        assert newer_after.json()["possible_duplicate"] is True
        assert newer_after.json()["duplicate_of_id"] == str(older.id)

    def test_retroactive_dedup_points_cluster_to_canonical_root(self, test_client):
        from app.db import get_db

        db = next(test_client.app.dependency_overrides[get_db]())
        canonical = _create_event(
            db,
            status="verified",
            business_name="Enlo Restaurant",
            city="Greenville",
            state="SC",
            address="123 Main St",
            event_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        first_duplicate = _create_event(
            db,
            status="candidate",
            business_name="Enlo",
            city="Greenville",
            state="SC",
            address="123 Main Street",
            event_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            possible_duplicate=True,
            duplicate_of_id=canonical.id,
        )
        newer_duplicate = _create_event(
            db,
            status="candidate",
            business_name="Enlo Cafe",
            city="Greenville",
            state="SC",
            address="123 Main Street",
            event_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
            created_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
        )

        resp = test_client.post("/api/admin/dedup/retroactive-run")
        assert resp.status_code == 200

        first_duplicate_after = test_client.get(f"/api/events/{first_duplicate.id}")
        assert first_duplicate_after.status_code == 200
        assert first_duplicate_after.json()["duplicate_of_id"] == str(canonical.id)

        newer_after = test_client.get(f"/api/events/{newer_duplicate.id}")
        assert newer_after.status_code == 200
        assert newer_after.json()["possible_duplicate"] is True
        assert newer_after.json()["duplicate_of_id"] == str(canonical.id)

    def test_merge_endpoint_same_source_target_422(self, test_client):
        from app.db import get_db

        db = next(test_client.app.dependency_overrides[get_db]())
        ev = _create_event(db, status="candidate", business_name="Same")

        resp = test_client.post(
            f"/api/admin/events/{ev.id}/merge",
            json={"target_id": str(ev.id), "canonical_fields": {}},
        )
        assert resp.status_code == 422

    def test_merge_endpoint_invalid_canonical_field_type_422(self, test_client):
        from app.db import get_db

        db = next(test_client.app.dependency_overrides[get_db]())
        source = _create_event(db, status="candidate", business_name="Source")
        target = _create_event(db, status="verified", business_name="Target")

        resp = test_client.post(
            f"/api/admin/events/{source.id}/merge",
            json={
                "target_id": str(target.id),
                "canonical_fields": {"event_date": "not-a-date"},
            },
        )
        assert resp.status_code == 422
