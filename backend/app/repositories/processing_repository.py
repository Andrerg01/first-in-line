"""Processing decisions repository — persistence for processing_decisions table.

All database access for ProcessingDecision records lives here.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.processing import ProcessingDecision


def create_processing_decision(db: Session, **kwargs: Any) -> ProcessingDecision:
    """Insert a new processing decision and return it.

    Args:
        db: Active database session.
        **kwargs: Column values for the new ProcessingDecision.

    Returns:
        The newly created ``ProcessingDecision`` instance.
    """
    decision = ProcessingDecision(**kwargs)
    db.add(decision)
    db.flush()
    return decision
