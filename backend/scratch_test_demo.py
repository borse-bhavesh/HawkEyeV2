import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import Base, engine, SessionLocal

client = TestClient(app)

def test_start_demo():
    res = client.post("/api/v1/video/demo")
    print("STATUS", res.status_code)
    print("BODY", res.json())
    assert res.status_code == 200

if __name__ == "__main__":
    test_start_demo()
