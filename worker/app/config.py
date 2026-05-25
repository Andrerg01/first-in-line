"""Worker settings — loaded from environment variables, with config.toml as defaults.

Precedence (highest → lowest):
  1. Environment variable
  2. config.toml (via :mod:`worker.app.app_config`)

Secrets (API keys, service URLs) must come from environment variables and are
never put in config.toml.
"""

from __future__ import annotations

import os

from worker.app.app_config import app_config


class WorkerSettings:
    """Configuration for the scheduled worker.

    All scraper-specific variables use the ``SCRAPER_`` prefix to match
    the deployment model documented in docs/project_plan/02_deployment_model.md.

    Tuneable parameters (models, timeouts, query limits) default to values
    from config.toml.  Environment variables take precedence, allowing
    per-deployment overrides without editing the config file.

    Secrets (openai_api_key, backend_api_url, mcp_server_url) come from
    environment variables only.
    """

    backend_api_url: str
    mcp_server_url: str
    target_location: str
    max_urls_per_run: int
    max_results_per_query: int
    request_timeout: float
    backoff_base: float
    max_retries: int
    query_interval_seconds: float
    llm_page_limit: int
    openai_api_key: str
    classify_model: str
    extract_model: str

    def __init__(self) -> None:
        # Secrets — env only, no config.toml fallback
        self.backend_api_url = os.environ.get(
            "BACKEND_API_URL", "http://backend-api:8000"
        )
        self.mcp_server_url = os.environ.get(
            "MCP_SERVER_URL", "http://mcp-server:9000"
        )
        self.openai_api_key = os.environ.get("OPENAI_API_KEY", "")

        # Tuneable params — env var overrides config.toml
        self.target_location = (
            os.environ.get("SCRAPER_TARGET_LOCATION")
            or app_config.search.target_location
        )
        self.max_urls_per_run = int(
            os.environ.get("SCRAPER_DAILY_PAGE_LIMIT")
            or app_config.search.daily_page_limit
        )
        self.max_results_per_query = int(
            os.environ.get("SCRAPER_MAX_RESULTS_PER_QUERY")
            or app_config.search.max_results_per_query
        )
        self.query_interval_seconds = float(
            os.environ.get("SCRAPER_RATE_LIMIT_SECONDS")
            or app_config.search.rate_limit_seconds
        )
        self.llm_page_limit = int(
            os.environ.get("SCRAPER_LLM_PAGE_LIMIT")
            or app_config.search.llm_page_limit
        )
        self.request_timeout = float(
            os.environ.get("WORKER_REQUEST_TIMEOUT")
            or app_config.worker.request_timeout
        )
        self.backoff_base = float(
            os.environ.get("WORKER_BACKOFF_BASE")
            or app_config.worker.backoff_base
        )
        self.max_retries = int(
            os.environ.get("WORKER_MAX_RETRIES")
            or app_config.worker.max_retries
        )
        self.classify_model = (
            os.environ.get("WORKER_CLASSIFY_MODEL")
            or app_config.llm.classify_model
        )
        self.extract_model = (
            os.environ.get("WORKER_EXTRACT_MODEL")
            or app_config.llm.extract_model
        )


settings = WorkerSettings()
