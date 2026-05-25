"""Search query templates for First In Line.

Templates and the version tag are loaded from ``config.toml`` at the
repository root.  Edit ``config.toml`` → ``[search]`` to add, remove, or
tweak queries without touching code.
"""

from __future__ import annotations

from worker.app.app_config import app_config

QUERY_SET_VERSION: str = app_config.search.query_set_version
_LOCATION: str = app_config.search.target_location
_TEMPLATES: list[str] = app_config.search.query_templates


def get_queries(location: str = _LOCATION) -> list[str]:
    """Return a list of fully-expanded search queries for the given location.

    Args:
        location: Location string to substitute into each template.

    Returns:
        A list of query strings ready to pass to the MCP web.search tool.
    """
    return [t.format(location=location) for t in _TEMPLATES]
