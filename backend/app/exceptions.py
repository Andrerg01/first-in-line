"""Domain exceptions for the Grand Opening Radar ingest pipeline.

Services raise these; the FastAPI exception handlers in ``main.py`` convert
them to the appropriate HTTP responses so that the service layer stays
transport-agnostic.
"""

from __future__ import annotations


class IngestError(Exception):
    """Base class for all ingest pipeline errors.

    Attributes:
        status_code: HTTP status code the exception handler should return.
    """

    status_code: int = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)


class MCPError(IngestError):
    """An MCP tool call returned an error or an unexpected response."""

    status_code = 502


class ExtractionError(IngestError):
    """OpenAI returned an error or produced output that failed validation."""

    status_code = 502


class ConfigurationError(IngestError):
    """The server is missing required configuration (e.g. an API key)."""

    status_code = 500
