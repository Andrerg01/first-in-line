"""Worker settings — loaded from environment variables."""

from __future__ import annotations

import os


class WorkerSettings:
    """Configuration for the scheduled worker.

    Reads from environment variables with sensible local-dev defaults.
    All scraper-specific variables use the ``SCRAPER_`` prefix to match
    the deployment model documented in docs/project_plan/02_deployment_model.md.

    Rate-limit protection:
        SCRAPER_RATE_LIMIT_SECONDS controls the mandatory pause between
        consecutive search queries.  The default (2 s) provides a conservative
        buffer; if the IP is actively rate-limited the actual cool-down must be
        handled externally (wait ~30–60 minutes before the next run).
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

    def __init__(self) -> None:
        self.backend_api_url = os.environ.get(
            "BACKEND_API_URL", "http://backend-api:8000"
        )
        self.mcp_server_url = os.environ.get(
            "MCP_SERVER_URL", "http://mcp-server:9000"
        )
        self.target_location = os.environ.get(
            "SCRAPER_TARGET_LOCATION", "Greenville, SC"
        )
        self.max_urls_per_run = int(
            os.environ.get("SCRAPER_DAILY_PAGE_LIMIT", "50")
        )
        self.max_results_per_query = int(
            os.environ.get("SCRAPER_MAX_RESULTS_PER_QUERY", "10")
        )
        self.request_timeout = float(os.environ.get("WORKER_REQUEST_TIMEOUT", "30.0"))
        self.backoff_base = float(os.environ.get("WORKER_BACKOFF_BASE", "1.0"))
        self.max_retries = int(os.environ.get("WORKER_MAX_RETRIES", "3"))
        self.query_interval_seconds = float(
            os.environ.get("SCRAPER_RATE_LIMIT_SECONDS", "2.0")
        )


settings = WorkerSettings()
