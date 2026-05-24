"""LangGraph extraction pipeline nodes.

Each node is a pure function that accepts an ``ExtractionState`` dict and
returns a partial dict of updates.  Nodes have no side-effects beyond
calling the OpenAI API; all persistence is handled outside the graph.

Node inventory:
- classify_relevance     — determine if a page describes a grand-opening event
- classify_event_count   — determine if page has one or multiple events
- extract_single_event   — extract a single event (single-event path)
- extract_multi_event    — extract multiple events (multi-event path)

Routing helpers (used in graph.py):
- route_after_relevance  — branch to event-count classification or END
- route_after_count      — branch to single or multi extraction or END
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from openai import OpenAI
from pydantic import ValidationError

from worker.app.extraction.prompts import (
    EVENT_COUNT_SYSTEM_PROMPT,
    EXTRACT_MULTI_SYSTEM_PROMPT,
    EXTRACT_SINGLE_SYSTEM_PROMPT,
    RELEVANCE_SYSTEM_PROMPT,
)
from worker.app.extraction.schemas import (
    EventCountResult,
    ExtractedEvent,
    LLMCallData,
    MultiEventExtractionResult,
    RelevanceResult,
    SingleEventExtractionResult,
)
from worker.app.extraction.state import ExtractionState

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cost estimation helpers
# ---------------------------------------------------------------------------

# Pricing per 1M tokens (USD) — update when OpenAI changes rates
_COST_PER_1M: dict[str, tuple[float, float]] = {
    # model: (input_cost_per_1m, output_cost_per_1m)
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
}


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Return estimated USD cost for a given call, or 0.0 if model unknown.

    Args:
        model: OpenAI model name.
        prompt_tokens: Number of prompt tokens used.
        completion_tokens: Number of completion tokens used.

    Returns:
        Estimated cost in USD.
    """
    rates = _COST_PER_1M.get(model)
    if rates is None:
        return 0.0
    input_rate, output_rate = rates
    return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000


# ---------------------------------------------------------------------------
# Internal LLM call helper
# ---------------------------------------------------------------------------


def _call_openai(
    client: OpenAI,
    *,
    call_type: str,
    model: str,
    system_prompt: str,
    user_content: str,
    schema_class: type,
) -> tuple[Any, LLMCallData]:
    """Make a single structured OpenAI call and return (parsed_result, call_data).

    Args:
        client: Configured ``OpenAI`` client.
        call_type: Identifier string stored in the LLM call record.
        model: Model name to use.
        system_prompt: System prompt string.
        user_content: User message content.
        schema_class: Pydantic model class to validate the LLM JSON output.

    Returns:
        A 2-tuple of (validated schema instance, LLMCallData).  On LLM error
        the first element is ``None`` and ``LLMCallData.status`` is ``"error"``.
    """
    t0 = time.monotonic()
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        if completion.usage:
            prompt_tokens = completion.usage.prompt_tokens
            completion_tokens = completion.usage.completion_tokens
            total_tokens = completion.usage.total_tokens

        raw_json = completion.choices[0].message.content or "{}"
        data = json.loads(raw_json)
        result = schema_class.model_validate(data)

        call_data = LLMCallData(
            call_type=call_type,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=_estimate_cost(model, prompt_tokens, completion_tokens),
            latency_ms=latency_ms,
            status="success",
        )
        return result, call_data

    except (ValidationError, json.JSONDecodeError) as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        log.error("LLM output validation failed for call_type=%s: %s", call_type, exc)
        call_data = LLMCallData(
            call_type=call_type,
            model=model,
            latency_ms=latency_ms,
            status="error",
            error_message=str(exc),
        )
        return None, call_data

    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        log.error("OpenAI call failed for call_type=%s: %s", call_type, exc)
        call_data = LLMCallData(
            call_type=call_type,
            model=model,
            latency_ms=latency_ms,
            status="error",
            error_message=str(exc),
        )
        return None, call_data


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------


def classify_relevance(state: ExtractionState, *, client: OpenAI, model: str) -> dict:
    """Classify whether the page describes a relevant grand-opening event.

    Args:
        state: Current extraction state.
        client: Configured ``OpenAI`` client.
        model: Model name to use for classification.

    Returns:
        State update dict with ``is_relevant``, ``relevance_reason``, and
        ``relevance_llm_call``.
    """
    text = (state.get("normalized_text") or "")[:6000]
    user_content = f"URL: {state.get('url', '')}\n\nPage text:\n{text}"

    result, call_data = _call_openai(
        client,
        call_type="classify_relevance",
        model=model,
        system_prompt=RELEVANCE_SYSTEM_PROMPT,
        user_content=user_content,
        schema_class=RelevanceResult,
    )

    if result is None:
        # LLM call failed — treat page as irrelevant to avoid bad data
        return {
            "is_relevant": False,
            "relevance_reason": f"Classification failed: {call_data.error_message}",
            "relevance_llm_call": call_data,
        }

    log.info(
        "classify_relevance: url=%s is_relevant=%s reason=%r",
        state.get("url"),
        result.is_relevant,
        result.reason,
    )
    return {
        "is_relevant": result.is_relevant,
        "relevance_reason": result.reason,
        "relevance_llm_call": call_data,
    }


def classify_event_count(
    state: ExtractionState, *, client: OpenAI, model: str
) -> dict:
    """Classify whether the page describes one event or multiple events.

    Args:
        state: Current extraction state (must have ``is_relevant=True``).
        client: Configured ``OpenAI`` client.
        model: Model name to use for classification.

    Returns:
        State update dict with ``event_count``, ``count_reason``, and
        ``count_llm_call``.
    """
    text = (state.get("normalized_text") or "")[:6000]
    user_content = f"URL: {state.get('url', '')}\n\nPage text:\n{text}"

    result, call_data = _call_openai(
        client,
        call_type="classify_event_count",
        model=model,
        system_prompt=EVENT_COUNT_SYSTEM_PROMPT,
        user_content=user_content,
        schema_class=EventCountResult,
    )

    if result is None:
        return {
            "event_count": "none",
            "count_reason": f"Classification failed: {call_data.error_message}",
            "count_llm_call": call_data,
        }

    log.info(
        "classify_event_count: url=%s event_count=%s count_estimate=%d",
        state.get("url"),
        result.event_count,
        result.count_estimate,
    )
    return {
        "event_count": result.event_count,
        "count_reason": result.reason,
        "count_llm_call": call_data,
    }


def extract_single_event(
    state: ExtractionState, *, client: OpenAI, model: str
) -> dict:
    """Extract a single structured event from the page.

    Args:
        state: Current extraction state (must have ``event_count="single"``).
        client: Configured ``OpenAI`` client.
        model: Model name to use for extraction.

    Returns:
        State update dict with ``extracted_events`` (list of one) and
        ``extraction_llm_call``.
    """
    text = (state.get("normalized_text") or "")[:8000]
    user_content = f"URL: {state.get('url', '')}\n\nPage text:\n{text}"

    result, call_data = _call_openai(
        client,
        call_type="extract_event",
        model=model,
        system_prompt=EXTRACT_SINGLE_SYSTEM_PROMPT,
        user_content=user_content,
        schema_class=SingleEventExtractionResult,
    )

    if result is None:
        return {
            "extracted_events": [],
            "extraction_llm_call": call_data,
            "error": f"Single-event extraction failed: {call_data.error_message}",
        }

    log.info(
        "extract_single_event: url=%s business_name=%r confidence=%.2f",
        state.get("url"),
        result.event.business_name,
        result.event.confidence_score,
    )
    return {
        "extracted_events": [result.event],
        "extraction_llm_call": call_data,
    }


def extract_multi_event(
    state: ExtractionState, *, client: OpenAI, model: str
) -> dict:
    """Extract multiple structured events from a multi-event page.

    Args:
        state: Current extraction state (must have ``event_count="multi"``).
        client: Configured ``OpenAI`` client.
        model: Model name to use for extraction.

    Returns:
        State update dict with ``extracted_events`` (list of N) and
        ``extraction_llm_call``.
    """
    text = (state.get("normalized_text") or "")[:10000]
    user_content = f"URL: {state.get('url', '')}\n\nPage text:\n{text}"

    result, call_data = _call_openai(
        client,
        call_type="extract_multi_event",
        model=model,
        system_prompt=EXTRACT_MULTI_SYSTEM_PROMPT,
        user_content=user_content,
        schema_class=MultiEventExtractionResult,
    )

    if result is None:
        return {
            "extracted_events": [],
            "extraction_llm_call": call_data,
            "error": f"Multi-event extraction failed: {call_data.error_message}",
        }

    log.info(
        "extract_multi_event: url=%s events_extracted=%d",
        state.get("url"),
        len(result.events),
    )
    return {
        "extracted_events": result.events,
        "extraction_llm_call": call_data,
    }


# ---------------------------------------------------------------------------
# Conditional routing helpers
# ---------------------------------------------------------------------------


def route_after_relevance(state: ExtractionState) -> str:
    """Return the next node name after relevance classification.

    Args:
        state: Current extraction state.

    Returns:
        ``"classify_event_count"`` if the page is relevant, ``"__end__"``
        otherwise.
    """
    return "classify_event_count" if state.get("is_relevant") else "__end__"


def route_after_count(state: ExtractionState) -> str:
    """Return the next node name after event-count classification.

    Args:
        state: Current extraction state.

    Returns:
        ``"extract_single_event"``, ``"extract_multi_event"``, or
        ``"__end__"`` based on ``event_count``.
    """
    count = state.get("event_count")
    if count == "single":
        return "extract_single_event"
    if count == "multi":
        return "extract_multi_event"
    return "__end__"
