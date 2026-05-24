"""Worker settings — loaded from environment variables."""

from __future__ import annotations

import os


class WorkerSettings:
    """Configuration for the scheduled worker.

    Reads from environment variables with sensible local-dev defaults.

    Rate-limit protection:
        QUERY_INTERVAL_SECONDS controls the mandatory pause between consecutive
        search queries.  The default (2 s) provides a conservative buffer when
        DuckDuckGo allows requests.  If the container IP is actively rate-limited
        (recognised by repeated timeouts from the MCP server) the worker logs a
        prominent WARNING — but the actual cool-down must be handled externally
        (wait ~30–60 minutes before the next run).
    """

    backend_api_url: str
    mcp_server_url: str
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
        self.max_urls_per_run = int(os.environ.get("MAX_URLS_PER_RUN", "50"))
        self.max_results_per_query = int(
            os.environ.get("MAX_RESULTS_PER_QUERY", "10")
        )
        self.request_timeout = float(os.environ.get("WORKER_REQUEST_TIMEOUT", "30.0"))
        self.backoff_base = float(os.environ.get("WORKER_BACKOFF_BASE", "1.0"))
        self.max_retries = int(os.environ.get("WORKER_MAX_RETRIES", "3"))
        self.query_interval_seconds = float(
            os.environ.get("QUERY_INTERVAL_SECONDS", "2.0")
        )


settings = WorkerSettings()
