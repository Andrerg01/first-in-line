"""Telemetry collection for one pipeline run.

The ``TelemetryCollector`` accumulates ``ToolCallRecord`` objects during a
run, then flushes them to the backend API in a single bulk request at the
end of the run.  This keeps individual tool-call code paths fast (no
synchronous DB round-trip per call) while still providing full observability.

Outcome codes
-------------
``success``   – call completed without error.
``error``     – call failed for a non-timeout, non-rate-limit reason.
``timeout``   – the HTTP request to the MCP server timed out.
``rate_limit``– the search provider returned a rate-limit response.
``duplicate`` – source document already exists (dedup skipped it).
``skipped``   – call was intentionally skipped (dry-run or cap reached).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

from worker.app.logger import get_logger

log = get_logger(__name__)

OutcomeCode = Literal[
    "success", "error", "timeout", "rate_limit", "duplicate", "skipped"
]


@dataclass
class ToolCallRecord:
    """One recorded tool call within a pipeline run."""

    tool_name: str
    input_summary: str
    outcome: OutcomeCode
    duration_ms: int
    http_status: int | None = None
    error_message: str | None = None
    attempt_number: int = 1


class TelemetryCollector:
    """Collects tool call records in memory for a single pipeline run.

    Example::

        collector = TelemetryCollector()
        t0 = collector.start_timer()
        try:
            result = mcp_client.search(query)
            collector.record(
                tool_name="web.search",
                input_summary=query[:200],
                outcome="success",
                duration_ms=collector.elapsed_ms(t0),
            )
        except Exception as exc:
            collector.record(
                tool_name="web.search",
                input_summary=query[:200],
                outcome=classify_outcome(exc),
                duration_ms=collector.elapsed_ms(t0),
                error_message=str(exc),
            )

    At the end of the run call ``collector.flush(run_id, api_fn)`` where
    ``api_fn`` is ``api_client.record_tool_calls``.
    """

    def __init__(self) -> None:
        self._records: list[ToolCallRecord] = []

    # ------------------------------------------------------------------
    # Timer helpers
    # ------------------------------------------------------------------

    @staticmethod
    def start_timer() -> float:
        """Return the current monotonic clock value as a float."""
        return time.monotonic()

    @staticmethod
    def elapsed_ms(t0: float) -> int:
        """Return milliseconds elapsed since *t0*.

        Args:
            t0: Monotonic start time returned by ``start_timer()``.

        Returns:
            Elapsed milliseconds as an integer.
        """
        return int((time.monotonic() - t0) * 1000)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        *,
        tool_name: str,
        input_summary: str,
        outcome: OutcomeCode,
        duration_ms: int,
        http_status: int | None = None,
        error_message: str | None = None,
        attempt_number: int = 1,
    ) -> None:
        """Append a tool call record to the in-memory buffer.

        Args:
            tool_name: Logical tool name, e.g. ``"web.search"``.
            input_summary: Truncated string describing the key input (query
                text, URL, etc.).  Will be truncated to 200 chars.
            outcome: Outcome code from the ``OutcomeCode`` literal.
            duration_ms: Wall-clock duration of the call in milliseconds.
            http_status: HTTP status code from the MCP or backend response,
                if available.
            error_message: Error detail string when outcome is not
                ``"success"``.
            attempt_number: Which retry attempt this record represents
                (1-indexed).
        """
        self._records.append(
            ToolCallRecord(
                tool_name=tool_name,
                input_summary=input_summary[:200],
                outcome=outcome,
                duration_ms=duration_ms,
                http_status=http_status,
                error_message=error_message,
                attempt_number=attempt_number,
            )
        )

    def count(self) -> int:
        """Return the number of buffered records."""
        return len(self._records)

    def as_dicts(self) -> list[dict]:
        """Serialise all buffered records to a list of plain dicts.

        Returns:
            List of dicts suitable for JSON serialisation.
        """
        return [
            {
                "tool_name": r.tool_name,
                "input_summary": r.input_summary,
                "outcome": r.outcome,
                "duration_ms": r.duration_ms,
                "http_status": r.http_status,
                "error_message": r.error_message,
                "attempt_number": r.attempt_number,
            }
            for r in self._records
        ]

    # ------------------------------------------------------------------
    # Flush
    # ------------------------------------------------------------------

    def flush(
        self,
        run_id: uuid.UUID,
        api_fn: "Callable[[uuid.UUID, list[dict]], None]",
    ) -> None:
        """Send all buffered records to the backend API and clear the buffer.

        Failures in flushing are logged as warnings but never re-raised so
        that telemetry problems never abort a pipeline run.

        Args:
            run_id: UUID of the parent search run.
            api_fn: Callable that accepts ``(run_id, records_list)`` and
                POSTs them to the backend.  Typically
                ``api_client.record_tool_calls``.
        """
        if not self._records:
            return
        try:
            count = len(self._records)
            api_fn(run_id, self.as_dicts())
            log.info("Flushed %d telemetry records for run %s", count, run_id)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "Failed to flush %d telemetry records for run %s: %s",
                len(self._records),
                run_id,
                exc,
            )
        finally:
            self._records.clear()


def classify_outcome(exc: Exception) -> OutcomeCode:
    """Map a caught exception to an ``OutcomeCode``.

    Uses the exception type and message to distinguish timeouts, rate-limit
    signals, and generic errors.  This is intentionally heuristic — the goal
    is observability, not perfect accuracy.

    Args:
        exc: The exception that was caught.

    Returns:
        An ``OutcomeCode`` string.
    """
    import httpx  # local import to avoid circular dependency

    msg = str(exc).lower()
    if isinstance(exc, httpx.TimeoutException) or "timed out" in msg or "timeout" in msg:
        return "timeout"
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
        return "rate_limit"
    if "rate" in msg and ("limit" in msg or "202" in msg):
        return "rate_limit"
    return "error"
