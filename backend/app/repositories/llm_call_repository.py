"""LLM call repository — persistence for the llm_calls table.

All database access for LLMCall records lives here.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.llm_calls import LLMCall
from app.schemas.llm_calls import LLMCallCreate


def create_llm_call(db: Session, payload: LLMCallCreate) -> LLMCall:
    """Insert a single LLM call record and flush (but do not commit).

    Args:
        db: Active database session.
        payload: Validated ``LLMCallCreate`` data.

    Returns:
        The newly created ``LLMCall`` instance.
    """
    record = LLMCall(**payload.model_dump())
    db.add(record)
    db.flush()
    return record


def bulk_create_llm_calls(
    db: Session, payloads: list[LLMCallCreate]
) -> list[LLMCall]:
    """Insert multiple LLM call records in one flush.

    Args:
        db: Active database session.
        payloads: List of validated ``LLMCallCreate`` items.

    Returns:
        List of created ``LLMCall`` instances in insertion order.
    """
    records = [LLMCall(**p.model_dump()) for p in payloads]
    db.add_all(records)
    db.flush()
    return records
