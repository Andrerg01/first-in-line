"""System prompts for the LangGraph extraction pipeline.

Prompts are loaded from ``config.toml`` at the repository root via
:mod:`worker.app.app_config`.  Edit ``config.toml`` to change prompt text;
no code changes are needed.
"""

from __future__ import annotations

from worker.app.app_config import app_config

RELEVANCE_SYSTEM_PROMPT: str = app_config.llm.prompts.relevance
EVENT_COUNT_SYSTEM_PROMPT: str = app_config.llm.prompts.event_count
EXTRACT_SINGLE_SYSTEM_PROMPT: str = app_config.llm.prompts.extract_single
EXTRACT_MULTI_SYSTEM_PROMPT: str = app_config.llm.prompts.extract_multi
