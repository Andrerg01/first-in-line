"""Unit tests for worker.app.telemetry — TelemetryCollector and classify_outcome."""
from __future__ import annotations

import time
import uuid
from unittest.mock import MagicMock

import pytest

from worker.app.telemetry import TelemetryCollector, classify_outcome


class TestTelemetryCollectorBasics:
    """TelemetryCollector record, count, as_dicts."""

    def test_starts_empty(self):
        c = TelemetryCollector()
        assert c.count() == 0
        assert c.as_dicts() == []

    def test_record_increments_count(self):
        c = TelemetryCollector()
        c.record(tool_name="web.search", input_summary="q", outcome="success", duration_ms=42)
        assert c.count() == 1

    def test_record_all_fields(self):
        c = TelemetryCollector()
        c.record(
            tool_name="web.fetch_page",
            input_summary="https://example.com",
            outcome="error",
            duration_ms=123,
            http_status=500,
            error_message="Internal error",
            attempt_number=2,
        )
        rows = c.as_dicts()
        assert len(rows) == 1
        row = rows[0]
        assert row["tool_name"] == "web.fetch_page"
        assert row["input_summary"] == "https://example.com"
        assert row["outcome"] == "error"
        assert row["duration_ms"] == 123
        assert row["http_status"] == 500
        assert row["error_message"] == "Internal error"
        assert row["attempt_number"] == 2

    def test_input_summary_truncated_to_200_chars(self):
        c = TelemetryCollector()
        long_input = "x" * 300
        c.record(tool_name="web.search", input_summary=long_input, outcome="success", duration_ms=1)
        row = c.as_dicts()[0]
        assert len(row["input_summary"]) == 200

    def test_multiple_records(self):
        c = TelemetryCollector()
        for i in range(5):
            c.record(tool_name=f"tool_{i}", input_summary="x", outcome="success", duration_ms=i)
        assert c.count() == 5
        names = [r["tool_name"] for r in c.as_dicts()]
        assert names == ["tool_0", "tool_1", "tool_2", "tool_3", "tool_4"]


class TestTelemetryCollectorTimer:
    """start_timer and elapsed_ms."""

    def test_start_timer_returns_float(self):
        c = TelemetryCollector()
        t0 = c.start_timer()
        assert isinstance(t0, float)

    def test_elapsed_ms_is_non_negative(self):
        c = TelemetryCollector()
        t0 = c.start_timer()
        elapsed = c.elapsed_ms(t0)
        assert elapsed >= 0

    def test_elapsed_ms_increases_over_time(self):
        c = TelemetryCollector()
        t0 = c.start_timer()
        time.sleep(0.05)  # 50ms
        elapsed = c.elapsed_ms(t0)
        assert elapsed >= 1  # at least 1ms elapsed


class TestTelemetryCollectorFlush:
    """flush behaviour — success and failure paths."""

    def test_flush_calls_api_fn_with_run_id_and_dicts(self):
        c = TelemetryCollector()
        c.record(tool_name="web.search", input_summary="q", outcome="success", duration_ms=10)
        run_id = uuid.uuid4()
        api_fn = MagicMock()

        c.flush(run_id, api_fn)

        api_fn.assert_called_once()
        call_run_id, call_dicts = api_fn.call_args[0]
        assert call_run_id == run_id
        assert len(call_dicts) == 1
        assert call_dicts[0]["tool_name"] == "web.search"

    def test_flush_clears_buffer_on_success(self):
        c = TelemetryCollector()
        c.record(tool_name="web.search", input_summary="q", outcome="success", duration_ms=10)
        api_fn = MagicMock()

        c.flush(uuid.uuid4(), api_fn)

        assert c.count() == 0

    def test_flush_clears_buffer_even_on_api_failure(self):
        c = TelemetryCollector()
        c.record(tool_name="web.search", input_summary="q", outcome="success", duration_ms=10)
        api_fn = MagicMock(side_effect=RuntimeError("network error"))

        # Should not raise
        c.flush(uuid.uuid4(), api_fn)

        assert c.count() == 0

    def test_flush_is_noop_when_empty(self):
        c = TelemetryCollector()
        api_fn = MagicMock()

        c.flush(uuid.uuid4(), api_fn)

        api_fn.assert_not_called()

    def test_flush_does_not_propagate_exception(self):
        c = TelemetryCollector()
        c.record(tool_name="web.search", input_summary="q", outcome="success", duration_ms=1)
        api_fn = MagicMock(side_effect=Exception("boom"))

        # Must not raise
        c.flush(uuid.uuid4(), api_fn)


class TestClassifyOutcome:
    """classify_outcome maps exceptions to outcome codes."""

    def test_timeout_from_message(self):
        exc = RuntimeError("request timed out")
        assert classify_outcome(exc) == "timeout"

    def test_timeout_from_timed_out_message(self):
        exc = RuntimeError("connection timed out after 30s")
        assert classify_outcome(exc) == "timeout"

    def test_generic_error(self):
        exc = ValueError("unexpected value")
        assert classify_outcome(exc) == "error"

    def test_runtime_error_without_timeout(self):
        exc = RuntimeError("connection refused")
        assert classify_outcome(exc) == "error"
