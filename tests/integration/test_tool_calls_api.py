"""Integration tests for the POST /api/ingest/search-run/{run_id}/tool-calls endpoint."""
from __future__ import annotations

import uuid

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_run(client) -> uuid.UUID:
    """Create a search run via the API and return its id."""
    resp = client.post(
        "/api/ingest/search-run",
        json={"run_type": "scheduled_daily", "query_set_version": "v1"},
    )
    assert resp.status_code == 201
    return uuid.UUID(resp.json()["id"])


def _minimal_tool_calls(n: int = 2) -> list[dict]:
    return [
        {
            "tool_name": "web.search",
            "input_summary": f"grand opening greenville sc {i}",
            "outcome": "success",
            "duration_ms": 123 + i,
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestAddToolCallsHappyPath:
    """POST /api/ingest/search-run/{run_id}/tool-calls — success cases."""

    def test_returns_201_with_saved_count(self, test_client):
        run_id = _create_run(test_client)
        payload = {"tool_calls": _minimal_tool_calls(3)}

        resp = test_client.post(
            f"/api/ingest/search-run/{run_id}/tool-calls",
            json=payload,
        )

        assert resp.status_code == 201
        assert resp.json()["saved"] == 3

    def test_all_outcome_codes_accepted(self, test_client):
        run_id = _create_run(test_client)
        outcome_codes = ["success", "error", "timeout", "rate_limit", "duplicate", "skipped"]
        tool_calls = [
            {
                "tool_name": "web.search",
                "input_summary": f"query {code}",
                "outcome": code,
                "duration_ms": 10,
            }
            for code in outcome_codes
        ]

        resp = test_client.post(
            f"/api/ingest/search-run/{run_id}/tool-calls",
            json={"tool_calls": tool_calls},
        )

        assert resp.status_code == 201
        assert resp.json()["saved"] == len(outcome_codes)

    def test_optional_fields_accepted(self, test_client):
        run_id = _create_run(test_client)
        tool_calls = [
            {
                "tool_name": "web.fetch_page",
                "input_summary": "https://example.com",
                "outcome": "error",
                "duration_ms": 456,
                "http_status": 500,
                "error_message": "Internal Server Error",
                "attempt_number": 2,
            }
        ]

        resp = test_client.post(
            f"/api/ingest/search-run/{run_id}/tool-calls",
            json={"tool_calls": tool_calls},
        )

        assert resp.status_code == 201
        assert resp.json()["saved"] == 1

    def test_empty_list_saves_zero(self, test_client):
        run_id = _create_run(test_client)

        resp = test_client.post(
            f"/api/ingest/search-run/{run_id}/tool-calls",
            json={"tool_calls": []},
        )

        assert resp.status_code == 201
        assert resp.json()["saved"] == 0


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

class TestAddToolCallsErrors:
    """POST /api/ingest/search-run/{run_id}/tool-calls — error cases."""

    def test_unknown_run_id_returns_404(self, test_client):
        unknown_id = uuid.uuid4()

        resp = test_client.post(
            f"/api/ingest/search-run/{unknown_id}/tool-calls",
            json={"tool_calls": _minimal_tool_calls(1)},
        )

        assert resp.status_code == 404

    def test_missing_tool_calls_key_returns_422(self, test_client):
        run_id = _create_run(test_client)

        resp = test_client.post(
            f"/api/ingest/search-run/{run_id}/tool-calls",
            json={},
        )

        assert resp.status_code == 422

    def test_invalid_outcome_code_returns_422(self, test_client):
        run_id = _create_run(test_client)

        resp = test_client.post(
            f"/api/ingest/search-run/{run_id}/tool-calls",
            json={
                "tool_calls": [
                    {
                        "tool_name": "web.search",
                        "input_summary": "q",
                        "outcome": "not_a_real_outcome",
                        "duration_ms": 10,
                    }
                ]
            },
        )

        assert resp.status_code == 422
