"""Repositories package for database CRUD operations."""

from app.repositories import (  # noqa: F401 – expose for easy import
    claims_repository,
    event_repository,
    processing_repository,
    search_repository,
    source_repository,
    telemetry_repository,
)
