"""Integration tests for the backend health endpoint."""
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_returns_200() -> None:
    """GET /health should return HTTP 200."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_status_ok() -> None:
    """GET /health body should be {"status": "ok"}."""
    response = client.get("/health")
    assert response.json() == {"status": "ok"}


def test_health_invalid_method_returns_405() -> None:
    """POST /health should return HTTP 405 (method not allowed)."""
    response = client.post("/health")
    assert response.status_code == 405
