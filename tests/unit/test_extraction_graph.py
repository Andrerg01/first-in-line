"""Unit tests for the LangGraph extraction graph (end-to-end flow, stubbed).

The graph is invoked with real LangGraph but all OpenAI client calls are
mocked at the node level so no credentials are required.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest


def _fake_completion(json_content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = json_content
    completion = MagicMock()
    completion.choices = [choice]
    completion.usage.prompt_tokens = 80
    completion.usage.completion_tokens = 40
    completion.usage.total_tokens = 120
    return completion


class TestExtractionGraphRelevantSingleEvent:
    """Full graph run: relevant page -> single event extracted."""

    def test_full_pipeline(self):
        call_responses = [
            '{"is_relevant": true, "reason": "grand opening"}',
            '{"event_count": "single", "count_estimate": 1, "reason": "one restaurant"}',
            '{"event": {"business_name": "Pizza Town", "event_type": "grand_opening", "category": "restaurant", "city": "Greenville", "state": "SC", "confidence_score": 0.9, "claims": []}}',
        ]
        call_index = {"i": 0}

        def fake_create(**kwargs):
            resp = _fake_completion(call_responses[call_index["i"]])
            call_index["i"] += 1
            return resp

        from worker.app.extraction.graph import build_extraction_graph

        with patch("worker.app.extraction.graph.OpenAI") as MockOpenAI:
            client = MagicMock()
            client.chat.completions.create.side_effect = fake_create
            MockOpenAI.return_value = client

            graph = build_extraction_graph(
                openai_api_key="test-key",
                classify_model="gpt-4o-mini",
                extract_model="gpt-4o-mini",
            )

        state = {
            "source_document_id": uuid.uuid4(),
            "search_run_id": uuid.uuid4(),
            "url": "https://example.com/pizza-town",
            "normalized_text": "Pizza Town grand opening next Friday in Greenville SC.",
            "extracted_events": [],
        }

        result = graph.invoke(state)

        assert result["is_relevant"] is True
        assert result["event_count"] == "single"
        assert len(result["extracted_events"]) == 1
        assert result["extracted_events"][0].business_name == "Pizza Town"
        assert result["relevance_llm_call"] is not None
        assert result["count_llm_call"] is not None
        assert result["extraction_llm_call"] is not None


class TestExtractionGraphIrrelevantPage:
    """Full graph run: irrelevant page -> stops after classify_relevance."""

    def test_stops_at_relevance(self):
        from worker.app.extraction.graph import build_extraction_graph

        with patch("worker.app.extraction.graph.OpenAI") as MockOpenAI:
            client = MagicMock()
            client.chat.completions.create.return_value = _fake_completion(
                '{"is_relevant": false, "reason": "job posting"}'
            )
            MockOpenAI.return_value = client

            graph = build_extraction_graph(
                openai_api_key="test-key",
                classify_model="gpt-4o-mini",
                extract_model="gpt-4o-mini",
            )

        state = {
            "source_document_id": uuid.uuid4(),
            "search_run_id": None,
            "url": "https://example.com/job",
            "normalized_text": "Now hiring cooks for our restaurant.",
            "extracted_events": [],
        }

        result = graph.invoke(state)

        assert result["is_relevant"] is False
        # Count and extraction nodes should not have run
        assert result.get("event_count") is None
        assert result.get("extracted_events") == []
        # Only ONE LLM call should have been made
        assert client.chat.completions.create.call_count == 1


class TestExtractionGraphMultiEvent:
    """Full graph run: relevant page with multiple events."""

    def test_multi_event_path(self):
        multi_json = """{
            "events": [
                {"business_name": "Bakery One", "event_type": "grand_opening",
                 "category": "cafe", "city": "Greenville", "state": "SC",
                 "confidence_score": 0.8, "claims": []},
                {"business_name": "Tacos Two", "event_type": "grand_opening",
                 "category": "restaurant", "city": "Greenville", "state": "SC",
                 "confidence_score": 0.75, "claims": []}
            ]
        }"""
        call_responses = [
            '{"is_relevant": true, "reason": "multiple grand openings"}',
            '{"event_count": "multi", "count_estimate": 2, "reason": "two businesses"}',
            multi_json,
        ]
        call_index = {"i": 0}

        def fake_create(**kwargs):
            resp = _fake_completion(call_responses[call_index["i"]])
            call_index["i"] += 1
            return resp

        from worker.app.extraction.graph import build_extraction_graph

        with patch("worker.app.extraction.graph.OpenAI") as MockOpenAI:
            client = MagicMock()
            client.chat.completions.create.side_effect = fake_create
            MockOpenAI.return_value = client

            graph = build_extraction_graph(
                openai_api_key="test-key",
                classify_model="gpt-4o-mini",
                extract_model="gpt-4o-mini",
            )

        state = {
            "source_document_id": uuid.uuid4(),
            "search_run_id": None,
            "url": "https://example.com/openings-roundup",
            "normalized_text": "Two new restaurants opening downtown.",
            "extracted_events": [],
        }

        result = graph.invoke(state)

        assert result["event_count"] == "multi"
        assert len(result["extracted_events"]) == 2
        names = {e.business_name for e in result["extracted_events"]}
        assert names == {"Bakery One", "Tacos Two"}
