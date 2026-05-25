"""Application configuration loaded from config.toml.

Config-file path resolution (highest priority first):

1. ``APP_CONFIG_PATH`` environment variable — set this in production or in
   automated tests that need an isolated config.
2. ``config.toml`` found by walking up the directory tree from this module —
   works for both local development and Docker containers where ``config.toml``
   is copied into the image WORKDIR.

Secrets (API keys, database URLs) are NOT stored in config.toml.  They belong
in .env / environment variables.  This module only reads non-secret tuneable
parameters.

Usage::

    from app.app_config import app_config
    model = app_config.llm.backend_model
    prompt = app_config.llm.prompts.manual_ingest
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Typed configuration dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AppMetaConfig:
    """Application identity — name and repository URL."""

    name: str
    repo_url: str


@dataclass(frozen=True)
class LLMPromptsConfig:
    """System prompts for each LLM call."""

    relevance: str
    event_count: str
    extract_single: str
    extract_multi: str
    manual_ingest: str


@dataclass(frozen=True)
class LLMConfig:
    """LLM model selection and sampling parameters."""

    classify_model: str
    extract_model: str
    backend_model: str
    temperature: float
    max_tokens: int
    prompts: LLMPromptsConfig


@dataclass(frozen=True)
class SearchConfig:
    """Search query templates and scraping budget parameters."""

    target_location: str
    query_set_version: str
    query_templates: list[str]
    max_results_per_query: int
    rate_limit_seconds: float
    daily_page_limit: int
    llm_page_limit: int


@dataclass(frozen=True)
class WorkerConfig:
    """Worker HTTP timeout and retry parameters."""

    request_timeout: float
    backoff_base: float
    max_retries: int


@dataclass(frozen=True)
class AppConfig:
    """Root configuration object."""

    meta: AppMetaConfig
    llm: LLMConfig
    search: SearchConfig
    worker: WorkerConfig


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def _find_config_path() -> Path:
    """Return the path to config.toml.

    Checks ``APP_CONFIG_PATH`` env var first, then walks up from this file's
    directory until ``config.toml`` is found.

    Raises:
        FileNotFoundError: When no config.toml can be located.
    """
    override = os.environ.get("APP_CONFIG_PATH")
    if override:
        return Path(override)

    here = Path(__file__).resolve().parent
    for candidate in (here, here.parent, here.parent.parent, here.parent.parent.parent):
        p = candidate / "config.toml"
        if p.exists():
            return p

    raise FileNotFoundError(
        "config.toml not found. Place it at the repository root or set"
        " the APP_CONFIG_PATH environment variable."
    )


def load_app_config() -> AppConfig:
    """Load and return application configuration from config.toml.

    Returns:
        Fully populated :class:`AppConfig` instance.

    Raises:
        FileNotFoundError: When config.toml cannot be located.
        KeyError: When a required config key is missing.
    """
    path = _find_config_path()
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    app_raw = raw["app"]
    llm_raw = raw["llm"]
    prompts_raw = llm_raw["prompts"]
    search_raw = raw["search"]
    worker_raw = raw["worker"]

    return AppConfig(
        meta=AppMetaConfig(
            name=app_raw["name"],
            repo_url=app_raw["repo_url"],
        ),
        llm=LLMConfig(
            classify_model=llm_raw["classify_model"],
            extract_model=llm_raw["extract_model"],
            backend_model=llm_raw["backend_model"],
            temperature=float(llm_raw["temperature"]),
            max_tokens=int(llm_raw["max_tokens"]),
            prompts=LLMPromptsConfig(
                relevance=prompts_raw["relevance"]["system"].strip(),
                event_count=prompts_raw["event_count"]["system"].strip(),
                extract_single=prompts_raw["extract_single"]["system"].strip(),
                extract_multi=prompts_raw["extract_multi"]["system"].strip(),
                manual_ingest=prompts_raw["manual_ingest"]["system"].strip(),
            ),
        ),
        search=SearchConfig(
            target_location=search_raw["target_location"],
            query_set_version=search_raw["query_set_version"],
            query_templates=list(search_raw["query_templates"]),
            max_results_per_query=int(search_raw["max_results_per_query"]),
            rate_limit_seconds=float(search_raw["rate_limit_seconds"]),
            daily_page_limit=int(search_raw["daily_page_limit"]),
            llm_page_limit=int(search_raw["llm_page_limit"]),
        ),
        worker=WorkerConfig(
            request_timeout=float(worker_raw["request_timeout"]),
            backoff_base=float(worker_raw["backoff_base"]),
            max_retries=int(worker_raw["max_retries"]),
        ),
    )


# Module-level singleton — loaded once at import time.
app_config: AppConfig = load_app_config()
