"""MCP server skeleton — exposes the approved narrow-tool catalog."""
from fastapi import FastAPI

app = FastAPI(title="Grand Opening Radar MCP Server", version="0.1.0")

TOOL_LIST = [
    "web.fetch_page",
    "web.normalize_text",
    "web.search",
    "geo.geocode_address",
    "db.find_source_by_hash",
    "db.find_similar_events",
    "db.insert_candidate_event",
]


@app.get("/health")
def health() -> dict[str, str]:
    """Return MCP server health status for uptime checks."""
    return {"status": "ok"}


@app.get("/tools")
def tools() -> dict[str, list[str]]:
    """Return the list of approved narrow tools exposed by this MCP server."""
    return {"tools": TOOL_LIST}
