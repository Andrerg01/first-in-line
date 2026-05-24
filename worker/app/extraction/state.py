"""LangGraph state definition for the extraction pipeline."""

from __future__ import annotations

import uuid
from typing import TypedDict

from worker.app.extraction.schemas import ExtractedEvent, LLMCallData


class ExtractionState(TypedDict, total=False):
    """State passed between LangGraph extraction nodes.

    All fields are optional (``total=False``) so individual nodes can add
    data incrementally without providing all fields at construction time.
    """

    # -- Inputs (set before the graph runs) --
    source_document_id: uuid.UUID
    search_run_id: uuid.UUID | None
    url: str
    normalized_text: str

    # -- Relevance classification outputs --
    is_relevant: bool | None
    relevance_reason: str | None
    relevance_llm_call: LLMCallData | None

    # -- Event-count classification outputs --
    event_count: str | None  # single | multi | none
    count_reason: str | None
    count_llm_call: LLMCallData | None

    # -- Extraction outputs --
    extracted_events: list[ExtractedEvent]
    extraction_llm_call: LLMCallData | None

    # -- Error / terminal state --
    error: str | None
