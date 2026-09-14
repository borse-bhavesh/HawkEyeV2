from fastapi.testclient import TestClient

import app.api.health as health_module
from app.main import app


client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "HAWKEYE V2"
    assert data["version"] == "2.0.0"
    assert data["status"] == "online"


def test_health_endpoint_database_online(monkeypatch):
    monkeypatch.setattr(
        health_module,
        "check_database_connection",
        lambda: True,
    )

    response = client.get("/api/v1/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "online"
    assert data["backend"] == "online"
    assert data["database"] == "online"


def test_health_endpoint_database_offline(monkeypatch):
    monkeypatch.setattr(
        health_module,
        "check_database_connection",
        lambda: False,
    )

    response = client.get("/api/v1/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "degraded"
    assert data["backend"] == "online"
    assert data["database"] == "offline"