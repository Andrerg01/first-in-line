"""Unit tests for the LangGraph extraction nodes.

All OpenAI calls are monkeypatched so these tests run without credentials.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from worker.app.extraction.nodes import (
    classify_event_count,
    classify_relevance,
    extract_multi_event,
    extract_single_event,
    route_after_count,
    route_after_relevance,
)
from worker.app.extraction.schemas import (
    EventCountResult,
    ExtractedClaim,
    ExtractedEvent,
    LLMCallData,
    MultiEventExtractionResult,
    RelevanceResult,
    SingleEventExtractionResult,
)
from worker.app.extraction.state import ExtractionState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_openai_response(json_content: str) -> MagicMock:
    """Build a minimal fake OpenAI completion response."""
    choice = MagicMock()
    choice.message.content = json_content
    completion = MagicMock()
    completion.choices = [choice]
    completion.usage.prompt_tokens = 100
    completion.usage.completion_tokens = 50
    completion.usage.total_tokens = 150
    return completion


def _make_client(json_content: str) -> MagicMock:
    """Return a fake OpenAI client whose create() returns a fixed response."""
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_openai_response(json_content)
    return client


def _base_state(**kwargs) -> ExtractionState:
    state: ExtractionState = {
        "source_document_id": uuid.uuid4(),
        "search_run_id": uuid.uuid4(),
        "url": "https://example.com/grand-opening",
        "normalized_text": "Burger Palace is opening its first Greenville SC location!",
        "extracted_events": [],
    }
    state.update(kwargs)  # type: ignore[arg-type]
    return state


# ---------------------------------------------------------------------------
# classify_relevance
# ---------------------------------------------------------------------------


class TestClassifyRelevance:
    def test_relevant_page(self):
        client = _make_client('{"is_relevant": true, "reason": "grand opening announced"}')
        state = _base_state()
        result = classify_relevance(state, client=client, model="gpt-4o-mini")
        assert result["is_relevant"] is True
        assert "grand opening" in result["relevance_reason"]
        assert isinstance(result["relevance_llm_call"], LLMCallData)
        assert result["relevance_llm_call"].status == "success"
        assert result["relevance_llm_call"].total_tokens == 150

    def test_irrelevant_page(self):
        client = _make_client('{"is_relevant": false, "reason": "job posting"}')
        state = _base_state()
        result = classify_relevance(state, client=client, model="gpt-4o-mini")
        assert result["is_relevant"] is False

    def test_openai_failure_treated_as_irrelevant(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("API error")
        state = _base_state()
        result = classify_relevance(state, client=client, model="gpt-4o-mini")
        assert result["is_relevant"] is False
        assert result["relevance_llm_call"].status == "error"

    def test_invalid_json_treated_as_irrelevant(self):
        client = _make_client("NOT VALID JSON")
        state = _base_state()
        result = classify_relevance(state, client=client, model="gpt-4o-mini")
        assert result["is_relevant"] is False
        assert result["relevance_llm_call"].status == "error"


# ---------------------------------------------------------------------------
# classify_event_count
# ---------------------------------------------------------------------------


class TestClassifyEventCount:
    def test_single_event(self):
        client = _make_client('{"event_count": "single", "count_estimate": 1, "reason": "one restaurant"}')
        state = _base_state(is_relevant=True)
        result = classify_event_count(state, client=client, model="gpt-4o-mini")
        assert result["event_count"] == "single"
        assert result["count_llm_call"].status == "success"

    def test_multi_event(self):
        client = _make_client('{"event_count": "multi", "count_estimate": 3, "reason": "three openings"}')
        state = _base_state(is_relevant=True)
        result = classify_event_count(state, client=client, model="gpt-4o-mini")
        assert result["event_count"] == "multi"

    def test_failure_defaults_to_none(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("timeout")
        state = _base_state(is_relevant=True)
        result = classify_event_count(state, client=client, model="gpt-4o-mini")
        assert result["event_count"] == "none"
        assert result["count_llm_call"].status == "error"


# ---------------------------------------------------------------------------
# extract_single_event
# ---------------------------------------------------------------------------


class TestExtractSingleEvent:
    _GOOD_JSON = """{
        "event": {
            "business_name": "Burger Palace",
            "event_name": null,
            "event_type": "grand_opening",
            "category": "restaurant",
            "event_date_str": "2026-07-04",
            "address": "123 Main St",
            "city": "Greenville",
            "state": "SC",
            "promotion_text": "Free burgers on opening day!",
            "confidence_score": 0.9,
            "claims": [
                {
                    "claim_type": "business_name",
                    "claim_value": "Burger Palace",
                    "claim_text": "Burger Palace is opening"
                }
            ]
        }
    }"""

    def test_successful_extraction(self):
        client = _make_client(self._GOOD_JSON)
        state = _base_state(is_relevant=True, event_count="single")
        result = extract_single_event(state, client=client, model="gpt-4o-mini")
        assert len(result["extracted_events"]) == 1
        event = result["extracted_events"][0]
        assert event.business_name == "Burger Palace"
        assert event.category == "restaurant"
        assert event.event_date_str == "2026-07-04"
        assert len(event.claims) == 1
        assert result["extraction_llm_call"].status == "success"

    def test_failure_returns_empty_list(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("API down")
        state = _base_state(is_relevant=True, event_count="single")
        result = extract_single_event(state, client=client, model="gpt-4o-mini")
        assert result["extracted_events"] == []
        assert result["extraction_llm_call"].status == "error"
        assert "error" in result


# ---------------------------------------------------------------------------
# extract_multi_event
# ---------------------------------------------------------------------------


class TestExtractMultiEvent:
    _GOOD_JSON = """{
        "events": [
            {
                "business_name": "Taco Town",
                "event_type": "grand_opening",
                "category": "restaurant",
                "city": "Greenville",
                "state": "SC",
                "confidence_score": 0.85,
                "claims": []
            },
            {
                "business_name": "Brew House",
                "event_type": "grand_opening",
                "category": "brewery",
                "city": "Greenville",
                "state": "SC",
                "confidence_score": 0.80,
                "claims": []
            }
        ]
    }"""

    def test_extracts_multiple_events(self):
        client = _make_client(self._GOOD_JSON)
        state = _base_state(is_relevant=True, event_count="multi")
        result = extract_multi_event(state, client=client, model="gpt-4o-mini")
        assert len(result["extracted_events"]) == 2
        names = {e.business_name for e in result["extracted_events"]}
        assert names == {"Taco Town", "Brew House"}

    def test_failure_returns_empty_list(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("timeout")
        state = _base_state(is_relevant=True, event_count="multi")
        result = extract_multi_event(state, client=client, model="gpt-4o-mini")
        assert result["extracted_events"] == []
        assert result["extraction_llm_call"].status == "error"


# ---------------------------------------------------------------------------
# Routing helpers
# ---------------------------------------------------------------------------


class TestRoutingHelpers:
    def test_route_after_relevance_relevant(self):
        assert route_after_relevance({"is_relevant": True}) == "classify_event_count"

    def test_route_after_relevance_irrelevant(self):
        assert route_after_relevance({"is_relevant": False}) == "__end__"

    def test_route_after_relevance_none(self):
        assert route_after_relevance({}) == "__end__"

    def test_route_after_count_single(self):
        assert route_after_count({"event_count": "single"}) == "extract_single_event"

    def test_route_after_count_multi(self):
        assert route_after_count({"event_count": "multi"}) == "extract_multi_event"

    def test_route_after_count_none(self):
        assert route_after_count({"event_count": "none"}) == "__end__"

    def test_route_after_count_missing(self):
        assert route_after_count({}) == "__end__"


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


class TestCostEstimation:
    def test_known_model_cost_estimate(self):
        from worker.app.extraction.nodes import _estimate_cost

        cost = _estimate_cost("gpt-4o-mini", prompt_tokens=1_000_000, completion_tokens=0)
        assert abs(cost - 0.15) < 0.001

    def test_unknown_model_returns_zero(self):
        from worker.app.extraction.nodes import _estimate_cost

        assert _estimate_cost("unknown-model-xyz", 1000, 500) == 0.0
