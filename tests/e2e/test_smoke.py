"""E2E smoke tests for the running Docker Compose stack.

Prerequisites:
    docker compose up -d

These tests are automatically skipped if the stack is not reachable,
so they are safe to run in any environment — they simply report as skipped
when the stack is down.
"""
import pytest
import httpx


BACKEND_URL = "http://localhost:8000"
MCP_URL = "http://localhost:9000"


def _service_reachable(url: str) -> bool:
    """Return True if the given base URL responds to a health check."""
    try:
        response = httpx.get(f"{url}/health", timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def stack_running() -> bool:
    """Session-scoped fixture: True if both core services are reachable."""
    return _service_reachable(BACKEND_URL) and _service_reachable(MCP_URL)


@pytest.mark.skipif(
    not _service_reachable(BACKEND_URL),
    reason="Backend not running — start with: docker compose up -d",
)
def test_backend_health() -> None:
    """Backend /health should return 200 and {"status": "ok"}."""
    response = httpx.get(f"{BACKEND_URL}/health", timeout=5.0)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.skipif(
    not _service_reachable(MCP_URL),
    reason="MCP server not running — start with: docker compose up -d",
)
def test_mcp_health() -> None:
    """MCP /health should return 200 and {"status": "ok"}."""
    response = httpx.get(f"{MCP_URL}/health", timeout=5.0)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.skipif(
    not _service_reachable(MCP_URL),
    reason="MCP server not running — start with: docker compose up -d",
)
def test_mcp_tools_returns_approved_catalog() -> None:
    """MCP /tools should return all currently approved and implemented tools."""
    response = httpx.get(f"{MCP_URL}/tools", timeout=5.0)
    assert response.status_code == 200
    tools = response.json()["tools"]
    expected = {
        "web.fetch_page",
        "web.normalize_text",
        "web.search",
    }
    assert expected.issubset(set(tools))


@pytest.mark.skipif(
    not _service_reachable(BACKEND_URL),
    reason="Backend not running — start with: docker compose up -d",
)
def test_events_list_endpoint_reachable() -> None:
    """GET /api/events should return 200 with a JSON array."""
    response = httpx.get(f"{BACKEND_URL}/api/events", timeout=5.0)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
