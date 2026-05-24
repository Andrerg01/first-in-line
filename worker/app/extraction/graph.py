"""LangGraph extraction graph definition.

Builds the extraction graph that processes a single source document through:
  1. classify_relevance   — filter irrelevant pages early (cheap)
  2. classify_event_count — determine single vs multi event (cheap)
  3. extract_single_event OR extract_multi_event — structured extraction

Usage::

    from worker.app.extraction.graph import build_extraction_graph
    from worker.app.extraction.state import ExtractionState

    graph = build_extraction_graph(
        openai_api_key="sk-...",
        classify_model="gpt-4o-mini",
        extract_model="gpt-4o-mini",
    )
    result: ExtractionState = graph.invoke(initial_state)
"""

from __future__ import annotations

import functools

from langgraph.graph import END, START, StateGraph
from openai import OpenAI

from worker.app.extraction.nodes import (
    classify_event_count,
    classify_relevance,
    extract_multi_event,
    extract_single_event,
    route_after_count,
    route_after_relevance,
)
from worker.app.extraction.state import ExtractionState


def build_extraction_graph(
    *,
    openai_api_key: str,
    classify_model: str = "gpt-4o-mini",
    extract_model: str = "gpt-4o-mini",
) -> "StateGraph":
    """Construct and compile the LangGraph extraction graph.

    Node functions are wrapped with ``functools.partial`` to inject the
    shared ``OpenAI`` client and model names.  This keeps nodes testable as
    pure functions while allowing the graph to carry shared state.

    Args:
        openai_api_key: OpenAI API key.
        classify_model: Model name for relevance and count classification nodes.
        extract_model: Model name for event extraction nodes.

    Returns:
        A compiled ``StateGraph[ExtractionState]`` ready to invoke.
    """
    client = OpenAI(api_key=openai_api_key, max_retries=2)

    graph = StateGraph(ExtractionState)

    # ------------------------------------------------------------------
    # Register nodes (partial-applied so they accept only (state,))
    # ------------------------------------------------------------------
    graph.add_node(
        "classify_relevance",
        functools.partial(classify_relevance, client=client, model=classify_model),
    )
    graph.add_node(
        "classify_event_count",
        functools.partial(classify_event_count, client=client, model=classify_model),
    )
    graph.add_node(
        "extract_single_event",
        functools.partial(extract_single_event, client=client, model=extract_model),
    )
    graph.add_node(
        "extract_multi_event",
        functools.partial(extract_multi_event, client=client, model=extract_model),
    )

    # ------------------------------------------------------------------
    # Edges
    # ------------------------------------------------------------------
    graph.add_edge(START, "classify_relevance")

    graph.add_conditional_edges(
        "classify_relevance",
        route_after_relevance,
        {
            "classify_event_count": "classify_event_count",
            "__end__": END,
        },
    )

    graph.add_conditional_edges(
        "classify_event_count",
        route_after_count,
        {
            "extract_single_event": "extract_single_event",
            "extract_multi_event": "extract_multi_event",
            "__end__": END,
        },
    )

    graph.add_edge("extract_single_event", END)
    graph.add_edge("extract_multi_event", END)

    return graph.compile()
