"""Worker settings — loaded from environment variables."""

from __future__ import annotations

import os


class WorkerSettings:
    """Configuration for the scheduled worker.

    Reads from environment variables with sensible local-dev defaults.
    """

    backend_api_url: str
    mcp_server_url: str
    max_urls_per_run: int
    max_results_per_query: int
    request_timeout: float
    backoff_base: float
    max_retries: int

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


settings = WorkerSettings()
