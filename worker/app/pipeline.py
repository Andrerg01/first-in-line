"""Worker pipeline -- orchestrates a single scheduled discovery run.

Flow:
1. Create a SearchRun record via the backend API.
2. For each query template, call MCP web.search and persist search results.
   A mandatory pause of QUERY_INTERVAL_SECONDS separates consecutive
   queries to reduce DuckDuckGo rate-limit exposure.
3. Collect unique canonical URLs from all results.
4. For each URL (up to MAX_URLS_PER_RUN):
   a. Call MCP web.fetch_page.
   b. Call MCP web.normalize_text to get the content hash.
   c. Call the backend API to store (or skip if duplicate) the source document.
5. Flush all telemetry (tool call records) to the backend API.
6. Mark the SearchRun as completed (or failed on error) with aggregate stats.

Telemetry:
  Every MCP tool call and backend API call is timed. Timing and outcome data
  accumulates in a TelemetryCollector during the run and is flushed once to
  POST /api/ingest/search-run/{run_id}/tool-calls before the run is closed.
  Telemetry flush failures are logged as warnings and never abort the run.

Rate-limit handling:
  If DuckDuckGo rate-limits the container, search queries will fail with a
  timeout. mcp_client.search() emits a prominent WARNING for each timed-out
  query. Failed queries are counted and the run ends with status partial.
  The rate limit typically clears after 30-60 minutes of inactivity.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from worker.app import api_client, mcp_client
from worker.app.config import settings
from worker.app.extraction.graph import build_extraction_graph
from worker.app.extraction.schemas import LLMCallData
from worker.app.extraction.state import ExtractionState
from worker.app.logger import RunLoggerAdapter, get_logger
from worker.app.search_queries import QUERY_SET_VERSION, get_queries
from worker.app.telemetry import TelemetryCollector, classify_outcome
from worker.app.url_utils import canonicalize_url, is_valid_http_url

_DIVIDER = chr(0x2550) * 60  # box-drawing double horizontal line (=)

log = get_logger(__name__)


def _fmt_elapsed(start: float) -> str:
    """Return elapsed wall-clock time as a [MM:SS] tag."""
    m, s = divmod(int(time.monotonic() - start), 60)
    return f"[{m:02d}:{s:02d}]"


def _eta(fetch_start: float, done: int, total: int) -> str:
    """Estimate remaining time for the fetch phase.

    Args:
        fetch_start: Monotonic time when the fetch phase began.
        done: Number of URLs already processed.
        total: Total URLs to process.

    Returns:
        Human-readable ETA string, e.g. ``ETA ~02:14``.
    """
    if done == 0:
        return "ETA estimating..."
    elapsed = time.monotonic() - fetch_start
    remaining = max(0, (total - done) * elapsed / done)
    m, s = divmod(int(remaining), 60)
    return f"ETA ~{m:02d}:{s:02d}"


def _p(msg: str = "") -> None:
    """Print a progress line to stdout immediately."""
    print(msg, flush=True)


@dataclass
class RunSummary:
    """Summary statistics for a completed discovery run."""

    run_id: uuid.UUID
    queries_executed: int = 0
    search_results_found: int = 0
    urls_attempted: int = 0
    source_docs_created: int = 0
    source_docs_skipped: int = 0
    fetch_errors: int = 0
    llm_pages_processed: int = 0
    events_created: int = 0
    pages_irrelevant: int = 0
    extraction_errors: int = 0
    final_status: str = "completed"
    notes: str = ""
    elapsed_seconds: float = 0.0


def run_once(*, dry_run: bool = False) -> RunSummary:
    """Execute one full discovery run and return a summary.

    Args:
        dry_run: When True, skip API/MCP calls and log what would happen.

    Returns:
        A ``RunSummary`` describing what was done.
    """
    start = time.monotonic()
    queries = get_queries(location=settings.target_location)
    collector = TelemetryCollector()

    _p(_DIVIDER)
    _p("  Grand Opening Radar -- Discovery Run")
    _p(f"  Location : {settings.target_location}")
    _p(f"  Queries  : {len(queries)}  |  URL cap: {settings.max_urls_per_run}  |  Dry run: {'Yes' if dry_run else 'No'}")
    _p(_DIVIDER)

    # ------------------------------------------------------------------
    # 1. Create SearchRun record
    # ------------------------------------------------------------------
    if not dry_run:
        run_record = api_client.create_search_run(
            run_type="scheduled_daily",
            query_set_version=QUERY_SET_VERSION,
        )
        run_id = run_record.id
    else:
        run_id = uuid.uuid4()

    log = get_logger(__name__, run_id=run_id)
    summary = RunSummary(run_id=run_id)
    log.info("Starting discovery run: run_id=%s dry_run=%s queries=%d", run_id, dry_run, len(queries))

    try:
        _execute_run(summary, run_log=log, dry_run=dry_run, start=start, queries=queries, collector=collector)
    except Exception as exc:  # noqa: BLE001
        log.error("Discovery run failed with unexpected error: %s", exc, exc_info=True)
        summary.final_status = "failed"
        summary.notes = str(exc)

    # ------------------------------------------------------------------
    # 5. Flush telemetry records
    # ------------------------------------------------------------------
    summary.elapsed_seconds = time.monotonic() - start

    if not dry_run:
        collector.flush(run_id, api_client.record_tool_calls)

    # ------------------------------------------------------------------
    # 6. Close the SearchRun with aggregate stats
    # ------------------------------------------------------------------
    if not dry_run:
        try:
            api_client.finish_search_run(
                run_id,
                status=summary.final_status,
                notes=summary.notes or None,
                queries_executed=summary.queries_executed,
                search_results_found=summary.search_results_found,
                urls_attempted=summary.urls_attempted,
                source_docs_created=summary.source_docs_created,
                source_docs_skipped=summary.source_docs_skipped,
                fetch_errors=summary.fetch_errors,
                elapsed_seconds=summary.elapsed_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to close SearchRun %s: %s", run_id, exc)

    log.info(
        "Run %s complete: status=%s queries=%d results=%d urls=%d "
        "created=%d skipped=%d errors=%d "
        "llm_pages=%d events=%d irrelevant=%d extraction_errors=%d",
        run_id,
        summary.final_status,
        summary.queries_executed,
        summary.search_results_found,
        summary.urls_attempted,
        summary.source_docs_created,
        summary.source_docs_skipped,
        summary.fetch_errors,
        summary.llm_pages_processed,
        summary.events_created,
        summary.pages_irrelevant,
        summary.extraction_errors,
    )
    return summary



def _execute_run(
    summary: RunSummary,
    *,
    run_log: RunLoggerAdapter,
    dry_run: bool,
    start: float,
    queries: list[str],
    collector: TelemetryCollector,
) -> None:
    """Inner run logic -- modifies summary in place.

    Args:
        summary: RunSummary to update with counts and status.
        run_log: Run-scoped logger carrying the run_id for all log lines.
        dry_run: Skip actual API/MCP calls when True.
        start: Monotonic start time used for elapsed-time formatting.
        queries: Search query strings to execute.
        collector: TelemetryCollector accumulating tool-call records.
    """
    seen_canonical: set[str] = set()
    ordered_urls: list[tuple[str, dict]] = []  # (canonical_url, meta)
    # Collect newly created source docs for LangGraph extraction
    new_source_docs: list[tuple[uuid.UUID, str, str]] = []  # (id, url, normalized_text)
    n_queries = len(queries)
    w = len(str(n_queries))  # width for zero-padded query index

    # ------------------------------------------------------------------
    # 2. Search phase
    # ------------------------------------------------------------------
    _p(f"\n{_fmt_elapsed(start)} SEARCH -- {n_queries} queries")

    for i, query in enumerate(queries, start=1):
        _p(f"{_fmt_elapsed(start)} +- Query {i:{w}d}/{n_queries}: {query!r}")
        run_log.info("Searching [%d/%d]: %r", i, n_queries, query)
        summary.queries_executed += 1

        if dry_run:
            _p(f"{_fmt_elapsed(start)} \\- [dry run] skipped")
            run_log.info("[dry_run] would call MCP web.search for %r", query)
            continue

        t0 = collector.start_timer()
        try:
            resp = mcp_client.search(query, max_results=settings.max_results_per_query)
            collector.record(
                tool_name="web.search",
                input_summary=query,
                outcome="success",
                duration_ms=collector.elapsed_ms(t0),
            )
            run_log.debug(
                "web.search: query=%r provider=%s results=%d duration_ms=%d",
                query,
                getattr(resp, "provider", "unknown"),
                len(resp.results),
                collector.elapsed_ms(t0),
            )
        except Exception as exc:  # noqa: BLE001
            collector.record(
                tool_name="web.search",
                input_summary=query,
                outcome=classify_outcome(exc),
                duration_ms=collector.elapsed_ms(t0),
                error_message=str(exc),
            )
            run_log.warning("Search failed for %r: %s", query, exc)
            _p(f"{_fmt_elapsed(start)} \\- x ERROR  {exc}")
            continue

        result_dicts: list[dict] = []
        new_this_query = 0
        for item in resp.results:
            if not is_valid_http_url(item.url):
                continue
            canonical = canonicalize_url(item.url)
            result_dicts.append(
                {
                    "query": query,
                    "rank": item.rank,
                    "title": item.title,
                    "url": item.url,
                    "snippet": item.snippet,
                    "search_provider": resp.provider,
                }
            )
            if canonical not in seen_canonical:
                seen_canonical.add(canonical)
                ordered_urls.append((canonical, {"url": item.url, "title": item.title}))
                new_this_query += 1

        if result_dicts:
            try:
                api_client.save_search_results(summary.run_id, result_dicts)
                summary.search_results_found += len(result_dicts)
                run_log.info("Saved %d results for %r", len(result_dicts), query)
            except Exception as exc:  # noqa: BLE001
                run_log.warning("Failed to save results for %r: %s", query, exc)

        _p(
            f"{_fmt_elapsed(start)} \\- -> {len(result_dicts)} results"
            f"  (+{new_this_query} new unique | {len(seen_canonical)} total unique)"
        )
        if i < n_queries and not dry_run and settings.query_interval_seconds > 0:
            run_log.debug(
                "Sleeping %.1fs between queries (SCRAPER_RATE_LIMIT_SECONDS)",
                settings.query_interval_seconds,
            )
            time.sleep(settings.query_interval_seconds)

    _p(
        f"\n{_fmt_elapsed(start)} Search done: "
        f"{summary.search_results_found} results | {len(seen_canonical)} unique URLs"
    )

    # ------------------------------------------------------------------
    # 3 & 4. Fetch phase
    # ------------------------------------------------------------------
    cap = settings.max_urls_per_run
    to_fetch = ordered_urls[:cap]
    n_to_fetch = len(to_fetch)
    uw = len(str(n_to_fetch)) if n_to_fetch else 1

    _p(f"\n{_fmt_elapsed(start)} FETCH -- {n_to_fetch} URLs (cap: {cap})")

    if n_to_fetch == 0:
        _p(f"{_fmt_elapsed(start)} Nothing to fetch.")
        return

    fetch_start = time.monotonic()

    for idx, (canonical_url, meta) in enumerate(to_fetch, start=1):
        fetch_url = meta["url"]
        title_preview = (meta.get("title") or "")[:70]
        summary.urls_attempted += 1
        eta_str = _eta(fetch_start, idx - 1, n_to_fetch)

        _p(f"{_fmt_elapsed(start)} +- URL {idx:{uw}d}/{n_to_fetch}  [{eta_str}]")
        _p(f"              {fetch_url[:90]}")
        if title_preview:
            _p(f"              {title_preview}")
        run_log.info("Fetching [%d/%d]: %s", idx, n_to_fetch, fetch_url)

        if dry_run:
            _p(f"{_fmt_elapsed(start)} \\- [dry run] skipped")
            run_log.info("[dry_run] would fetch %s", fetch_url)
            continue

        # ---- web.fetch_page ----
        t0 = collector.start_timer()
        try:
            fetch_resp = mcp_client.fetch_page(fetch_url)
            run_log.debug(
                "web.fetch_page: url=%s status=%s http=%s duration_ms=%d",
                fetch_url,
                fetch_resp.fetch_status,
                fetch_resp.http_status,
                collector.elapsed_ms(t0),
            )
        except Exception as exc:  # noqa: BLE001
            collector.record(
                tool_name="web.fetch_page",
                input_summary=fetch_url,
                outcome=classify_outcome(exc),
                duration_ms=collector.elapsed_ms(t0),
                error_message=str(exc),
            )
            run_log.warning("Fetch error for %s: %s", fetch_url, exc)
            summary.fetch_errors += 1
            _p(f"{_fmt_elapsed(start)} \\- x FETCH ERROR  {exc}")
            _p(_running_totals(summary))
            continue

        if fetch_resp.fetch_status != "success" or not fetch_resp.visible_text:
            collector.record(
                tool_name="web.fetch_page",
                input_summary=fetch_url,
                outcome="error",
                duration_ms=collector.elapsed_ms(t0),
                http_status=fetch_resp.http_status,
                error_message=fetch_resp.error_message or fetch_resp.fetch_status,
            )
            run_log.info(
                "Fetch non-success for %s: status=%s error=%s",
                fetch_url, fetch_resp.fetch_status, fetch_resp.error_message,
            )
            summary.fetch_errors += 1
            detail = fetch_resp.error_message or "no visible text extracted"
            _p(f"{_fmt_elapsed(start)} \\- x SKIP  {detail}")
            _p(_running_totals(summary))
            continue

        collector.record(
            tool_name="web.fetch_page",
            input_summary=fetch_url,
            outcome="success",
            duration_ms=collector.elapsed_ms(t0),
            http_status=fetch_resp.http_status,
        )

        # ---- web.normalize_text ----
        t0 = collector.start_timer()
        try:
            norm_resp = mcp_client.normalize_text(fetch_resp.visible_text)
            collector.record(
                tool_name="web.normalize_text",
                input_summary=f"{len(fetch_resp.visible_text)} chars from {fetch_url}",
                outcome="success",
                duration_ms=collector.elapsed_ms(t0),
            )
            run_log.debug(
                "web.normalize_text: url=%s hash=%s duration_ms=%d",
                fetch_url,
                (norm_resp.text_hash or "")[:8],
                collector.elapsed_ms(t0),
            )
        except Exception as exc:  # noqa: BLE001
            collector.record(
                tool_name="web.normalize_text",
                input_summary=fetch_url,
                outcome=classify_outcome(exc),
                duration_ms=collector.elapsed_ms(t0),
                error_message=str(exc),
            )
            run_log.warning("Normalize error for %s: %s", fetch_url, exc)
            summary.fetch_errors += 1
            _p(f"{_fmt_elapsed(start)} \\- x NORMALIZE ERROR  {exc}")
            _p(_running_totals(summary))
            continue

        # ---- db.store_source_document ----
        t0 = collector.start_timer()
        try:
            store_result = api_client.store_source_document(
                url=fetch_url,
                canonical_url=fetch_resp.canonical_url or canonical_url,
                domain=fetch_resp.domain,
                title=fetch_resp.title,
                visible_text=norm_resp.normalized_text,
                visible_text_hash=norm_resp.text_hash,
                http_status=fetch_resp.http_status,
                content_type=fetch_resp.content_type,
                fetch_status=fetch_resp.fetch_status,
                error_message=fetch_resp.error_message,
                search_run_id=summary.run_id,
            )
        except Exception as exc:  # noqa: BLE001
            collector.record(
                tool_name="db.store_source_document",
                input_summary=fetch_url,
                outcome=classify_outcome(exc),
                duration_ms=collector.elapsed_ms(t0),
                error_message=str(exc),
            )
            run_log.warning("Store error for %s: %s", fetch_url, exc)
            summary.fetch_errors += 1
            _p(f"{_fmt_elapsed(start)} \\- x STORE ERROR  {exc}")
            _p(_running_totals(summary))
            continue

        if store_result.created:
            collector.record(
                tool_name="db.store_source_document",
                input_summary=fetch_url,
                outcome="success",
                duration_ms=collector.elapsed_ms(t0),
            )
            summary.source_docs_created += 1
            short_hash = (norm_resp.text_hash or "")[:8]
            run_log.info(
                "New source doc stored: id=%s hash=%s url=%s",
                store_result.source_document_id, short_hash, fetch_url,
            )
            _p(f"{_fmt_elapsed(start)} \\- ok NEW    hash:{short_hash}")
            # Queue for LangGraph extraction
            new_source_docs.append(
                (store_result.source_document_id, fetch_url, norm_resp.normalized_text)
            )
        else:
            collector.record(
                tool_name="db.store_source_document",
                input_summary=fetch_url,
                outcome="duplicate",
                duration_ms=collector.elapsed_ms(t0),
            )
            summary.source_docs_skipped += 1
            run_log.info(
                "Duplicate skipped: id=%s url=%s",
                store_result.source_document_id, fetch_url,
            )
            _p(f"{_fmt_elapsed(start)} \\- dup: SKIP   already in database")

        _p(_running_totals(summary))

    if summary.fetch_errors > 0 or (summary.search_results_found == 0 and not dry_run):
        summary.final_status = "partial"
    else:
        summary.final_status = "completed"

    # ------------------------------------------------------------------
    # 5. LangGraph extraction phase
    # ------------------------------------------------------------------
    to_extract = new_source_docs[: settings.llm_page_limit]
    n_to_extract = len(to_extract)

    _p(f"\n{_fmt_elapsed(start)} EXTRACT -- {n_to_extract} new pages (LLM cap: {settings.llm_page_limit})")

    if n_to_extract == 0 or dry_run:
        if dry_run and new_source_docs:
            _p(f"{_fmt_elapsed(start)} [dry run] would extract {len(new_source_docs)} pages")
        elif n_to_extract == 0:
            _p(f"{_fmt_elapsed(start)} Nothing to extract.")
        return

    if not settings.openai_api_key:
        run_log.warning("OPENAI_API_KEY not set — skipping extraction phase")
        _p(f"{_fmt_elapsed(start)} WARNING: OPENAI_API_KEY not set; skipping extraction")
        return

    graph = build_extraction_graph(
        openai_api_key=settings.openai_api_key,
        classify_model=settings.classify_model,
        extract_model=settings.extract_model,
    )
    ew = len(str(n_to_extract))

    for eidx, (source_doc_id, fetch_url, normalized_text) in enumerate(to_extract, start=1):
        _p(f"{_fmt_elapsed(start)} +- Extract {eidx:{ew}d}/{n_to_extract}: {fetch_url[:80]}")
        run_log.info("Extracting [%d/%d]: %s", eidx, n_to_extract, fetch_url)
        summary.llm_pages_processed += 1

        initial_state: ExtractionState = {
            "source_document_id": source_doc_id,
            "search_run_id": summary.run_id,
            "url": fetch_url,
            "normalized_text": normalized_text,
            "extracted_events": [],
        }

        try:
            final_state: ExtractionState = graph.invoke(initial_state)
        except Exception as exc:  # noqa: BLE001
            run_log.error("Extraction graph error for %s: %s", fetch_url, exc)
            summary.extraction_errors += 1
            _p(f"{_fmt_elapsed(start)} \\- x GRAPH ERROR  {exc}")
            continue

        # Collect all LLM calls from this graph run
        all_llm_calls: list[LLMCallData] = []
        for field in ("relevance_llm_call", "count_llm_call", "extraction_llm_call"):
            call_data = final_state.get(field)  # type: ignore[literal-required]
            if call_data is not None:
                all_llm_calls.append(call_data)

        extracted_events = final_state.get("extracted_events") or []

        if not final_state.get("is_relevant"):
            run_log.info(
                "Page irrelevant: url=%s reason=%r",
                fetch_url,
                final_state.get("relevance_reason"),
            )
            summary.pages_irrelevant += 1
            _p(f"{_fmt_elapsed(start)} \\- IRRELEVANT  {final_state.get('relevance_reason', '')[:60]}")
            # Still save LLM calls via an irrelevant candidate submission
            # (no claims → backend marks as irrelevant and only logs LLM records)
            if all_llm_calls:
                try:
                    api_client.save_candidate_event(
                        source_doc_id,
                        search_run_id=summary.run_id,
                        business_name=None,
                        event_name=None,
                        event_type="unknown",
                        category=None,
                        event_date_str=None,
                        address=None,
                        city=None,
                        state=None,
                        promotion_text=None,
                        confidence_score=0.0,
                        claims=[],
                        llm_calls=[c.model_dump() for c in all_llm_calls],
                    )
                except Exception as exc:  # noqa: BLE001
                    run_log.warning("Failed to save irrelevant LLM calls for %s: %s", fetch_url, exc)
            continue

        if not extracted_events:
            run_log.warning(
                "Extraction returned no events for relevant page: url=%s error=%s",
                fetch_url, final_state.get("error"),
            )
            summary.extraction_errors += 1
            _p(f"{_fmt_elapsed(start)} \\- x NO EVENTS  {final_state.get('error', '')[:60]}")
            continue

        # Save one candidate per extracted event (multi-event support)
        for event in extracted_events:
            try:
                result = api_client.save_candidate_event(
                    source_doc_id,
                    search_run_id=summary.run_id,
                    business_name=event.business_name,
                    event_name=event.event_name,
                    event_type=event.event_type,
                    category=event.category,
                    event_date_str=event.event_date_str,
                    address=event.address,
                    city=event.city,
                    state=event.state,
                    promotion_text=event.promotion_text,
                    confidence_score=event.confidence_score,
                    claims=[c.model_dump() for c in event.claims],
                    llm_calls=[c.model_dump() for c in all_llm_calls],
                )
                if result.created:
                    summary.events_created += 1
                    run_log.info(
                        "Candidate event created: event_id=%s business=%r url=%s",
                        result.event_id, event.business_name, fetch_url,
                    )
                    _p(
                        f"{_fmt_elapsed(start)} \\- NEW EVENT  "
                        f"{(event.business_name or '?')[:50]}  "
                        f"conf:{event.confidence_score:.2f}"
                    )
                elif result.duplicate:
                    run_log.info("Duplicate event skipped: url=%s", fetch_url)
                    _p(f"{_fmt_elapsed(start)} \\- dup EVENT  already recorded")
            except Exception as exc:  # noqa: BLE001
                run_log.error("Failed to save candidate event for %s: %s", fetch_url, exc)
                summary.extraction_errors += 1
                _p(f"{_fmt_elapsed(start)} \\- x SAVE ERROR  {exc}")



def _running_totals(summary: RunSummary) -> str:
    """Format a compact running-totals line for display during the fetch phase."""
    return (
        f"              "
        f"new: {summary.source_docs_created}  "
        f"skipped: {summary.source_docs_skipped}  "
        f"errors: {summary.fetch_errors}"
    )
