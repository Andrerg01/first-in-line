"""Seed data script — populates the database with a representative sample event.

Usage (run from the backend/ directory with DATABASE_URL set):

    python seed_data.py

The script is idempotent: running it a second time will skip insertion
if a seed event with the same business name and city already exists.
"""

import os
import sys
import uuid
from datetime import datetime, timezone

# Allow importing app package when running from backend/.
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import (  # noqa: F401 — ensure all models are registered
    Event,
    EventClaim,
    EventSource,
    Location,
    ProcessingDecision,
    SearchResult,
    SearchRun,
    SourceDocument,
)
from app.db import Base


def _build_engine():
    url = settings.database_url
    if not url:
        print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
        sys.exit(1)
    return create_engine(url)


def seed(session) -> None:
    """Insert seed location, event, source document, and claims.

    Args:
        session: An active SQLAlchemy session.
    """
    # --- Location ---------------------------------------------------------
    location = session.query(Location).filter_by(city="Greenville", state="SC").first()
    if location is None:
        location = Location(
            id=uuid.uuid4(),
            name="Greenville, SC",
            city="Greenville",
            state="SC",
            country="US",
            lat=34.8526,
            lon=-82.3940,
            radius_miles=25.0,
        )
        session.add(location)
        session.flush()
        print(f"  Created location: {location.name}")
    else:
        print(f"  Location already exists: {location.name}")

    # --- Event ------------------------------------------------------------
    existing = (
        session.query(Event)
        .filter_by(business_name="The Seed Biscuit Co.", city="Greenville")
        .first()
    )
    if existing:
        print(f"  Seed event already exists: {existing.business_name} (id={existing.id})")
        return

    event = Event(
        id=uuid.uuid4(),
        business_name="The Seed Biscuit Co.",
        event_name="Grand Opening",
        event_type="grand_opening",
        category="cafe",
        event_date=datetime(2026, 7, 4, 10, 0, tzinfo=timezone.utc),
        address="123 Main St",
        city="Greenville",
        state="SC",
        country="US",
        lat=34.8500,
        lon=-82.3950,
        promotion_text="Free biscuit with any purchase on opening day!",
        status="candidate",
        confidence_score=0.87,
    )
    session.add(event)
    session.flush()
    print(f"  Created event: {event.business_name} (id={event.id})")

    # --- Source document --------------------------------------------------
    source = SourceDocument(
        id=uuid.uuid4(),
        url="https://example.com/the-seed-biscuit-co-grand-opening",
        canonical_url="https://example.com/the-seed-biscuit-co-grand-opening",
        domain="example.com",
        title="The Seed Biscuit Co. Opens July 4th in Greenville",
        fetched_at=datetime.now(timezone.utc),
        visible_text=(
            "Join us for the grand opening of The Seed Biscuit Co. on July 4th, 2026. "
            "Located at 123 Main St, Greenville SC. Free biscuit with any purchase!"
        ),
        visible_text_hash="abc123seed",
        fetch_status="success",
        http_status=200,
        content_type="text/html",
        fetch_method="requests",
    )
    session.add(source)
    session.flush()
    print(f"  Created source document: {source.url} (id={source.id})")

    # --- Event source link ------------------------------------------------
    link = EventSource(
        id=uuid.uuid4(),
        event_id=event.id,
        source_document_id=source.id,
        relationship_type="primary_source",
    )
    session.add(link)

    # --- Claims -----------------------------------------------------------
    claims_data = [
        {
            "claim_type": "business_name",
            "claim_value": "The Seed Biscuit Co.",
            "claim_text": "grand opening of The Seed Biscuit Co.",
            "confidence_score": 0.97,
        },
        {
            "claim_type": "event_date",
            "claim_value": "2026-07-04",
            "claim_text": "on July 4th, 2026",
            "confidence_score": 0.91,
        },
        {
            "claim_type": "address",
            "claim_value": "123 Main St, Greenville SC",
            "claim_text": "Located at 123 Main St, Greenville SC",
            "confidence_score": 0.88,
        },
        {
            "claim_type": "promotion",
            "claim_value": "Free biscuit with any purchase",
            "claim_text": "Free biscuit with any purchase!",
            "confidence_score": 0.85,
        },
    ]
    for c in claims_data:
        claim = EventClaim(
            id=uuid.uuid4(),
            event_id=event.id,
            source_document_id=source.id,
            **c,
        )
        session.add(claim)

    session.flush()
    print(f"  Created {len(claims_data)} claims for event {event.id}")


def main() -> None:
    """Entry point: connect, seed, commit."""
    engine = _build_engine()
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with Session() as session:
        with session.begin():
            seed(session)
    print("Seed complete.")


if __name__ == "__main__":
    main()
