import pytest
from fastapi.testclient import TestClient

from app.main import app

@pytest.fixture(scope="module")
def api_client():
    with TestClient(app) as c:
        yield c

def test_cors_vercel_origin_allowed(api_client):
    headers = {
        "Origin": "https://hawk-eye-v2.vercel.app",
        "Access-Control-Request-Method": "GET",
    }
    response = api_client.options("/api/v1/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://hawk-eye-v2.vercel.app"
    assert "GET" in response.headers.get("access-control-allow-methods", "")

def test_cors_localhost_allowed(api_client):
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
    }
    response = api_client.options("/api/v1/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"

def test_cors_disallowed_origin(api_client):
    headers = {
        "Origin": "https://random-site.com",
        "Access-Control-Request-Method": "GET",
    }
    response = api_client.options("/api/v1/health", headers=headers)
    assert response.status_code == 400
    # Or in FastAPI default CORS middleware, disallowed origins usually don't get the ACA-Origin header
    # But for a preflight, if the origin is not allowed, the response is usually a 400 Bad Request
