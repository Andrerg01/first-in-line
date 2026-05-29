"""ORM models package.

Import all model classes here so that Alembic's ``autogenerate`` can
discover them when it imports ``app.models``.
"""

from app.models.claims import EventClaim  # noqa: F401
from app.models.events import Event  # noqa: F401
from app.models.llm_calls import LLMCall  # noqa: F401
from app.models.locations import Location  # noqa: F401
from app.models.processing import ProcessingDecision  # noqa: F401
from app.models.search import SearchResult, SearchRun  # noqa: F401
from app.models.sources import EventSource, SourceDocument  # noqa: F401
from app.models.telemetry import PipelineToolCall  # noqa: F401
from app.models.users import User, UserProfile, UserCredentialHistory, UserPreferredLocation, SearchLocation  # noqa: F401

__all__ = [
    "Location",
    "SearchRun",
    "SearchResult",
    "SourceDocument",
    "Event",
    "EventSource",
    "EventClaim",
    "ProcessingDecision",
    "LLMCall",
    "PipelineToolCall",
]
