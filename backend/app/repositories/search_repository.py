"""Search repository — persistence access for search_runs and search_results.

All database queries for SearchRun and SearchResult records live here.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.search import SearchResult, SearchRun


def create_search_run(
    db: Session,
    *,
    run_type: str,
    location_id: uuid.UUID | None = None,
    query_set_version: str | None = None,
    notes: str | None = None,
) -> SearchRun:
    """Insert a new SearchRun record with status=running.

    Args:
        db: Active database session.
        run_type: One of 'scheduled_daily', 'manual_search', 'backfill'.
        location_id: Optional FK to locations table.
        query_set_version: Version label for the query template set used.
        notes: Optional free-text annotation.

    Returns:
        The persisted ``SearchRun`` instance.
    """
    now = datetime.now(timezone.utc)
    run = SearchRun(
        location_id=location_id,
        run_type=run_type,
        status="running",
        started_at=now,
        query_set_version=query_set_version,
        notes=notes,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def update_search_run_status(
    db: Session,
    run_id: uuid.UUID,
    *,
    status: str,
    notes: str | None = None,
    queries_executed: int | None = None,
    search_results_found: int | None = None,
    urls_attempted: int | None = None,
    source_docs_created: int | None = None,
    source_docs_skipped: int | None = None,
    fetch_errors: int | None = None,
    elapsed_seconds: float | None = None,
) -> SearchRun | None:
    """Update the status, finished_at, and aggregate stats of a SearchRun.

    Args:
        db: Active database session.
        run_id: UUID of the SearchRun to update.
        status: New status string (completed | failed | partial | cancelled).
        notes: Optional notes to append or set.
        queries_executed: Number of queries that ran.
        search_results_found: Total search result rows stored.
        urls_attempted: Number of URLs fetch was attempted for.
        source_docs_created: New source documents created.
        source_docs_skipped: Duplicate documents skipped.
        fetch_errors: Number of fetch/store errors.
        elapsed_seconds: Total wall-clock seconds for the run.

    Returns:
        The updated ``SearchRun``, or ``None`` if not found.
    """
    run = db.get(SearchRun, run_id)
    if run is None:
        return None
    run.status = status
    run.finished_at = datetime.now(timezone.utc)
    if notes is not None:
        run.notes = notes
    if queries_executed is not None:
        run.queries_executed = queries_executed
    if search_results_found is not None:
        run.search_results_found = search_results_found
    if urls_attempted is not None:
        run.urls_attempted = urls_attempted
    if source_docs_created is not None:
        run.source_docs_created = source_docs_created
    if source_docs_skipped is not None:
        run.source_docs_skipped = source_docs_skipped
    if fetch_errors is not None:
        run.fetch_errors = fetch_errors
    if elapsed_seconds is not None:
        run.elapsed_seconds = elapsed_seconds
    db.commit()
    db.refresh(run)
    return run


def create_search_result(
    db: Session,
    *,
    search_run_id: uuid.UUID,
    query: str | None,
    rank: int | None,
    title: str | None,
    url: str,
    snippet: str | None,
    search_provider: str | None,
) -> SearchResult:
    """Insert a single SearchResult record for a given run.

    Args:
        db: Active database session.
        search_run_id: FK to the parent SearchRun.
        query: The query string that produced this result.
        rank: Position of this result in the provider's ranked list.
        title: Page title from the search result.
        url: URL of the search result.
        snippet: Short description excerpt from the provider.
        search_provider: Name of the search provider (e.g. 'duckduckgo').

    Returns:
        The persisted ``SearchResult`` instance.
    """
    result = SearchResult(
        search_run_id=search_run_id,
        query=query,
        rank=rank,
        title=title,
        url=url,
        snippet=snippet,
        search_provider=search_provider,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


def get_search_run(db: Session, run_id: uuid.UUID) -> SearchRun | None:
    """Return a SearchRun by primary key, or None.

    Args:
        db: Active database session.
        run_id: UUID primary key.

    Returns:
        The matching ``SearchRun`` or ``None``.
    """
    return db.get(SearchRun, run_id)


def list_search_runs(db: Session, *, limit: int = 50) -> list[SearchRun]:
    """Return the most recent SearchRuns ordered by started_at descending.

    Args:
        db: Active database session.
        limit: Maximum number of rows to return.

    Returns:
        A list of ``SearchRun`` instances.
    """
    stmt = (
        select(SearchRun)
        .order_by(SearchRun.started_at.desc().nullslast())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())
