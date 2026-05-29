"""Search run and search result ORM models.

search_runs — tracks each scheduled or manual discovery run.
search_results — stores search result metadata before page fetching.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SearchRun(Base):
    """A single discovery run scoped to a location."""

    __tablename__ = "search_runs"
    __table_args__ = {"schema": "ingestion"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ingestion.locations.id", ondelete="SET NULL"), nullable=True
    )
    run_type: Mapped[str] = mapped_column(
        String(40), nullable=False
    )  # manual_url | scheduled_daily | manual_search | backfill
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="running"
    )  # running | completed | failed | partial | cancelled
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    query_set_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Aggregate stats populated when the run finishes.
    queries_executed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    search_results_found: Mapped[int | None] = mapped_column(Integer, nullable=True)
    urls_attempted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_docs_created: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_docs_skipped: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetch_errors: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elapsed_seconds: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    results: Mapped[list["SearchResult"]] = relationship(
        "SearchResult", back_populates="search_run", cascade="all, delete-orphan"
    )


class SearchResult(Base):
    """Raw search result metadata produced during a search run."""

    __tablename__ = "search_results"
    __table_args__ = {"schema": "ingestion"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    search_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ingestion.search_runs.id", ondelete="CASCADE"), nullable=False
    )
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_provider: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    search_run: Mapped["SearchRun"] = relationship("SearchRun", back_populates="results")
