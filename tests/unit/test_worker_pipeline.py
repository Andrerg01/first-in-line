"""Unit tests for the worker pipeline (run_once).

All external calls (MCP and backend API) are monkeypatched so no network
or database is required.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from worker.app import pipeline
from worker.app.api_client import SearchRunRecord, SourceDocumentResult
from worker.app.mcp_client import (
    FetchPageResponse,
    NormalizeTextResponse,
    SearchResponse,
    SearchResultItem,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_search_response(query: str, urls: list[str]) -> SearchResponse:
    return SearchResponse(
        query=query,
        provider="stub",
        results=[
            SearchResultItem(rank=i + 1, title=f"Title {i}", url=u, snippet="snippet")
            for i, u in enumerate(urls)
        ],
    )


def _make_fetch_response(url: str, text: str = "visible text") -> FetchPageResponse:
    return FetchPageResponse(
        url=url,
        canonical_url=url,
        domain="example.com",
        title="Page Title",
        visible_text=text,
        http_status=200,
        content_type="text/html",
        fetch_status="success",
        error_message=None,
    )


def _make_normalize_response(text_hash: str = "abc123") -> NormalizeTextResponse:
    return NormalizeTextResponse(normalized_text="normalised text", text_hash=text_hash)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRunOnceDryRun:
    """run_once with dry_run=True should not call any external services."""

    def test_dry_run_returns_summary_without_calls(self, monkeypatch):
        called = []

        monkeypatch.setattr(pipeline.api_client, "create_search_run", lambda **kw: called.append("create"))
        monkeypatch.setattr(pipeline.mcp_client, "search", lambda q, **kw: called.append("search"))

        summary = pipeline.run_once(dry_run=True)

        assert "create" not in called
        assert "search" not in called
        assert isinstance(summary.run_id, uuid.UUID)


class TestRunOnceHappyPath:
    """run_once with a mocked environment that produces new source docs."""

    def test_creates_source_docs_for_unique_urls(self, monkeypatch):
        run_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        monkeypatch.setattr(
            pipeline.api_client, "create_search_run",
            lambda **kw: SearchRunRecord(id=run_id, status="running"),
        )
        monkeypatch.setattr(pipeline.api_client, "finish_search_run", lambda *a, **kw: None)
        monkeypatch.setattr(pipeline.api_client, "record_tool_calls", lambda *a, **kw: 0)
        monkeypatch.setattr(
            pipeline.api_client, "save_search_results",
            lambda run_id, results: len(results),
        )
        monkeypatch.setattr(
            pipeline.api_client, "store_source_document",
            lambda **kw: SourceDocumentResult(
                created=True, source_document_id=doc_id, duplicate=False
            ),
        )
        monkeypatch.setattr(
            pipeline.mcp_client, "search",
            lambda q, **kw: _make_search_response(q, ["https://example.com/a"]),
        )
        monkeypatch.setattr(
            pipeline.mcp_client, "fetch_page",
            lambda url: _make_fetch_response(url),
        )
        monkeypatch.setattr(
            pipeline.mcp_client, "normalize_text",
            lambda text: _make_normalize_response("hash1"),
        )
        monkeypatch.setattr(pipeline.time, "sleep", lambda s: None)

        summary = pipeline.run_once(dry_run=False)

        assert summary.source_docs_created >= 1
        assert summary.final_status == "completed"
        assert summary.run_id == run_id

    def test_skips_duplicate_urls_across_queries(self, monkeypatch):
        """Same canonical URL appearing in multiple query results is fetched only once."""
        run_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        fetch_calls: list[str] = []

        monkeypatch.setattr(
            pipeline.api_client, "create_search_run",
            lambda **kw: SearchRunRecord(id=run_id, status="running"),
        )
        monkeypatch.setattr(pipeline.api_client, "finish_search_run", lambda *a, **kw: None)
        monkeypatch.setattr(pipeline.api_client, "record_tool_calls", lambda *a, **kw: 0)
        monkeypatch.setattr(pipeline.api_client, "save_search_results", lambda *a, **kw: 1)
        monkeypatch.setattr(
            pipeline.api_client, "store_source_document",
            lambda **kw: SourceDocumentResult(
                created=True, source_document_id=doc_id, duplicate=False
            ),
        )

        # All queries return the same URL
        monkeypatch.setattr(
            pipeline.mcp_client, "search",
            lambda q, **kw: _make_search_response(q, ["https://example.com/same-page"]),
        )

        def track_fetch(url):
            fetch_calls.append(url)
            return _make_fetch_response(url)

        monkeypatch.setattr(pipeline.mcp_client, "fetch_page", track_fetch)
        monkeypatch.setattr(
            pipeline.mcp_client, "normalize_text",
            lambda text: _make_normalize_response("samehash"),
        )
        monkeypatch.setattr(pipeline.time, "sleep", lambda s: None)

        pipeline.run_once(dry_run=False)

        # The same canonical URL should only be fetched once regardless of
        # how many queries returned it.
        assert fetch_calls.count("https://example.com/same-page") == 1

    def test_duplicate_store_result_records_duplicate_outcome(self, monkeypatch):
        """When store_source_document returns created=False, outcome should be 'duplicate'."""
        run_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        recorded_outcomes: list[str] = []

        original_record = None

        monkeypatch.setattr(
            pipeline.api_client, "create_search_run",
            lambda **kw: SearchRunRecord(id=run_id, status="running"),
        )
        monkeypatch.setattr(pipeline.api_client, "finish_search_run", lambda *a, **kw: None)
        monkeypatch.setattr(pipeline.api_client, "record_tool_calls", lambda *a, **kw: 0)
        monkeypatch.setattr(pipeline.api_client, "save_search_results", lambda *a, **kw: 1)
        # Return created=False to simulate a duplicate
        monkeypatch.setattr(
            pipeline.api_client, "store_source_document",
            lambda **kw: SourceDocumentResult(
                created=False, source_document_id=doc_id, duplicate=True
            ),
        )
        monkeypatch.setattr(
            pipeline.mcp_client, "search",
            lambda q, **kw: _make_search_response(q, ["https://example.com/dup"]),
        )
        monkeypatch.setattr(pipeline.mcp_client, "fetch_page", lambda url: _make_fetch_response(url))
        monkeypatch.setattr(
            pipeline.mcp_client, "normalize_text",
            lambda text: _make_normalize_response("duphash"),
        )
        monkeypatch.setattr(pipeline.time, "sleep", lambda s: None)

        # Intercept telemetry records
        from worker.app.telemetry import TelemetryCollector
        original_record_fn = TelemetryCollector.record

        def tracking_record(self, *, tool_name, input_summary, outcome, **kw):
            recorded_outcomes.append((tool_name, outcome))
            original_record_fn(self, tool_name=tool_name, input_summary=input_summary, outcome=outcome, **kw)

        monkeypatch.setattr(TelemetryCollector, "record", tracking_record)

        summary = pipeline.run_once(dry_run=False)

        store_outcomes = [o for name, o in recorded_outcomes if name == "db.store_source_document"]
        assert "duplicate" in store_outcomes
        assert summary.source_docs_skipped >= 1

    def test_fetch_errors_set_partial_status(self, monkeypatch):
        """Any fetch error — even with some successes — should produce 'partial' status."""
        run_id = uuid.uuid4()
        call_count = 0

        monkeypatch.setattr(
            pipeline.api_client, "create_search_run",
            lambda **kw: SearchRunRecord(id=run_id, status="running"),
        )
        monkeypatch.setattr(pipeline.api_client, "finish_search_run", lambda *a, **kw: None)
        monkeypatch.setattr(pipeline.api_client, "record_tool_calls", lambda *a, **kw: 0)
        monkeypatch.setattr(pipeline.api_client, "save_search_results", lambda *a, **kw: 1)
        monkeypatch.setattr(
            pipeline.api_client, "store_source_document",
            lambda **kw: SourceDocumentResult(
                created=True, source_document_id=uuid.uuid4(), duplicate=False
            ),
        )
        monkeypatch.setattr(
            pipeline.mcp_client, "search",
            lambda q, **kw: _make_search_response(q, [
                "https://example.com/ok",
                "https://example.com/fail",
            ]),
        )

        def mixed_fetch(url):
            if "fail" in url:
                raise RuntimeError("fetch error")
            return _make_fetch_response(url)

        monkeypatch.setattr(pipeline.mcp_client, "fetch_page", mixed_fetch)
        monkeypatch.setattr(
            pipeline.mcp_client, "normalize_text",
            lambda text: _make_normalize_response("hash1"),
        )
        monkeypatch.setattr(pipeline.time, "sleep", lambda s: None)

        summary = pipeline.run_once(dry_run=False)

        assert summary.source_docs_created >= 1
        assert summary.fetch_errors >= 1
        assert summary.final_status == "partial"


class TestRunOnceFetchError:
    """run_once gracefully handles fetch failures."""

    def test_fetch_failure_increments_error_count(self, monkeypatch):
        run_id = uuid.uuid4()

        monkeypatch.setattr(
            pipeline.api_client, "create_search_run",
            lambda **kw: SearchRunRecord(id=run_id, status="running"),
        )
        monkeypatch.setattr(pipeline.api_client, "finish_search_run", lambda *a, **kw: None)
        monkeypatch.setattr(pipeline.api_client, "record_tool_calls", lambda *a, **kw: 0)
        monkeypatch.setattr(pipeline.api_client, "save_search_results", lambda *a, **kw: 1)
        monkeypatch.setattr(pipeline.time, "sleep", lambda s: None)

        monkeypatch.setattr(
            pipeline.mcp_client, "search",
            lambda q, **kw: _make_search_response(q, ["https://example.com/fail"]),
        )
        monkeypatch.setattr(
            pipeline.mcp_client, "fetch_page",
            lambda url: (_ for _ in ()).throw(RuntimeError("timeout")),
        )

        summary = pipeline.run_once(dry_run=False)

        assert summary.fetch_errors >= 1

    def test_search_failure_is_logged_and_skipped(self, monkeypatch):
        run_id = uuid.uuid4()

        monkeypatch.setattr(
            pipeline.api_client, "create_search_run",
            lambda **kw: SearchRunRecord(id=run_id, status="running"),
        )
        monkeypatch.setattr(pipeline.api_client, "finish_search_run", lambda *a, **kw: None)
        monkeypatch.setattr(pipeline.api_client, "record_tool_calls", lambda *a, **kw: 0)
        monkeypatch.setattr(pipeline.time, "sleep", lambda s: None)

        monkeypatch.setattr(
            pipeline.mcp_client, "search",
            lambda q, **kw: (_ for _ in ()).throw(RuntimeError("rate limited")),
        )

        # Should not raise
        summary = pipeline.run_once(dry_run=False)
        assert summary.queries_executed > 0
        assert summary.search_results_found == 0


class TestRunOnceCliIntegration:
    """CLI cmd_run_once returns correct exit codes."""

    def test_returns_zero_on_success(self, monkeypatch):
        monkeypatch.setattr(
            pipeline, "run_once",
            lambda **kw: _SummaryStub("completed"),
        )
        from worker.app.cli import cmd_run_once
        assert cmd_run_once(dry_run=False) == 0

    def test_returns_one_on_failed(self, monkeypatch):
        monkeypatch.setattr(
            pipeline, "run_once",
            lambda **kw: _SummaryStub("failed"),
        )
        from worker.app.cli import cmd_run_once
        assert cmd_run_once(dry_run=False) == 1

    def test_returns_one_on_partial(self, monkeypatch):
        monkeypatch.setattr(
            pipeline, "run_once",
            lambda **kw: _SummaryStub("partial"),
        )
        from worker.app.cli import cmd_run_once
        assert cmd_run_once(dry_run=False) == 1


class _SummaryStub:
    """Minimal stub mimicking RunSummary for CLI tests."""

    def __init__(self, final_status: str) -> None:
        self.run_id = uuid.uuid4()
        self.final_status = final_status
        self.queries_executed = 0
        self.search_results_found = 0
        self.urls_attempted = 0
        self.source_docs_created = 0
        self.source_docs_skipped = 0
        self.fetch_errors = 0
        self.elapsed_seconds = 0.0
        self.notes = ""
