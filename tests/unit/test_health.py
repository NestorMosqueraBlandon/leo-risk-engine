from fastapi.testclient import TestClient

from leo_risk.interface.http.app import app

client = TestClient(app)


def test_health_returns_200() -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_ok() -> None:
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "ok"


def test_ready_returns_200() -> None:
    response = client.get("/ready")
    assert response.status_code == 200


def test_ready_contains_version() -> None:
    response = client.get("/ready")
    data = response.json()
    assert "version" in data
    assert "uptime_seconds" in data
    assert data["status"] == "ready"
