"""Search query templates for Grand Opening Radar.

Generates a set of search queries targeting grand opening and new business
announcements in Greenville, SC.  The template set is versioned so the DB
can record which version was used for each search run.
"""

from __future__ import annotations

QUERY_SET_VERSION = "v1"

# Location scope for Phase 4.
_LOCATION = "Greenville SC"

# Query templates.  Each ``{location}`` placeholder is replaced at runtime.
_TEMPLATES: list[str] = [
    "grand opening restaurant {location}",
    "new restaurant opening {location}",
    "new cafe opening {location}",
    "new brewery opening {location}",
    "grand opening food truck {location}",
    "new retail store opening {location}",
    "opening soon restaurant {location}",
    "opening soon {location}",
    "new business opening {location}",
]


def get_queries(location: str = _LOCATION) -> list[str]:
    """Return a list of fully-expanded search queries for the given location.

    Args:
        location: Location string to substitute into each template.

    Returns:
        A list of query strings ready to pass to the MCP web.search tool.
    """
    return [t.format(location=location) for t in _TEMPLATES]
