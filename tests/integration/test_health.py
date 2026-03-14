"""GET /api/v1/health returns 200 and success body."""

from fastapi.testclient import TestClient

from backend.app import app


def test_health_returns_200_and_ok() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
