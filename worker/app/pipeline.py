"""Worker pipeline — orchestrates a single scheduled discovery run.

Flow:
1. Create a SearchRun record via the backend API.
2. For each query template, call MCP web.search and persist search results.
3. Collect unique canonical URLs from all results.
4. For each URL (up to MAX_URLS_PER_RUN):
   a. Call MCP web.fetch_page.
   b. Call MCP web.normalize_text to get the content hash.
   c. Call the backend API to store (or skip if duplicate) the source document.
5. Mark the SearchRun as completed (or failed on error).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from worker.app import api_client, mcp_client
from worker.app.config import settings
from worker.app.search_queries import QUERY_SET_VERSION, get_queries
from worker.app.url_utils import canonicalize_url, is_valid_http_url

log = logging.getLogger(__name__)


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
    final_status: str = "completed"
    notes: str = ""


def run_once(*, dry_run: bool = False) -> RunSummary:
    """Execute one full discovery run and return a summary.

    Args:
        dry_run: When True, skip API/MCP calls and log what would happen.

    Returns:
        A ``RunSummary`` describing what was done.
    """
    log.info("Starting discovery run (dry_run=%s)", dry_run)

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

    summary = RunSummary(run_id=run_id)
    log.info("SearchRun created: id=%s", run_id)

    try:
        _execute_run(summary, dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001
        log.error("Discovery run failed with unexpected error: %s", exc, exc_info=True)
        summary.final_status = "failed"
        summary.notes = str(exc)

    # ------------------------------------------------------------------
    # 5. Close the SearchRun
    # ------------------------------------------------------------------
    if not dry_run:
        try:
            api_client.finish_search_run(
                run_id,
                status=summary.final_status,
                notes=summary.notes or None,
            )
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to close SearchRun %s: %s", run_id, exc)

    log.info(
        "Run %s complete: status=%s queries=%d results=%d urls=%d created=%d skipped=%d errors=%d",
        run_id,
        summary.final_status,
        summary.queries_executed,
        summary.search_results_found,
        summary.urls_attempted,
        summary.source_docs_created,
        summary.source_docs_skipped,
        summary.fetch_errors,
    )
    return summary


def _execute_run(summary: RunSummary, *, dry_run: bool) -> None:
    """Inner run logic — modifies summary in place.

    Args:
        summary: RunSummary to update with counts and status.
        dry_run: Skip actual API/MCP calls when True.
    """
    queries = get_queries()
    seen_canonical: set[str] = set()
    ordered_urls: list[tuple[str, dict]] = []  # (canonical_url, result_dict)

    # ------------------------------------------------------------------
    # 2. Search phase
    # ------------------------------------------------------------------
    for query in queries:
        log.info("Searching: %r", query)
        summary.queries_executed += 1

        if dry_run:
            log.info("[dry_run] would call MCP web.search for %r", query)
            continue

        try:
            resp = mcp_client.search(query, max_results=settings.max_results_per_query)
        except Exception as exc:  # noqa: BLE001
            log.warning("Search failed for %r: %s", query, exc)
            continue

        result_dicts: list[dict] = []
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

        if result_dicts:
            try:
                api_client.save_search_results(summary.run_id, result_dicts)
                summary.search_results_found += len(result_dicts)
                log.info("Saved %d results for %r", len(result_dicts), query)
            except Exception as exc:  # noqa: BLE001
                log.warning("Failed to save results for %r: %s", query, exc)

    # ------------------------------------------------------------------
    # 3 & 4. Fetch phase
    # ------------------------------------------------------------------
    cap = settings.max_urls_per_run
    to_fetch = ordered_urls[:cap]
    log.info("Fetching %d unique URLs (cap=%d)", len(to_fetch), cap)

    for canonical_url, meta in to_fetch:
        fetch_url = meta["url"]  # original URL with any UTM params, etc.
        summary.urls_attempted += 1
        log.info("Fetching: %s", fetch_url)

        if dry_run:
            log.info("[dry_run] would fetch %s", fetch_url)
            continue

        try:
            fetch_resp = mcp_client.fetch_page(fetch_url)
        except Exception as exc:  # noqa: BLE001
            log.warning("Fetch error for %s: %s", fetch_url, exc)
            summary.fetch_errors += 1
            continue

        if fetch_resp.fetch_status != "success" or not fetch_resp.visible_text:
            log.info(
                "Fetch non-success for %s: status=%s error=%s",
                fetch_url, fetch_resp.fetch_status, fetch_resp.error_message,
            )
            summary.fetch_errors += 1
            continue

        try:
            norm_resp = mcp_client.normalize_text(fetch_resp.visible_text)
        except Exception as exc:  # noqa: BLE001
            log.warning("Normalize error for %s: %s", fetch_url, exc)
            summary.fetch_errors += 1
            continue

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
            log.warning("Store error for %s: %s", fetch_url, exc)
            summary.fetch_errors += 1
            continue

        if store_result.created:
            summary.source_docs_created += 1
            log.info("New source doc stored: id=%s url=%s", store_result.source_document_id, fetch_url)
        else:
            summary.source_docs_skipped += 1
            log.info("Duplicate skipped: id=%s url=%s", store_result.source_document_id, fetch_url)

    if summary.fetch_errors > 0 and summary.source_docs_created == 0:
        summary.final_status = "partial"
    else:
        summary.final_status = "completed"
