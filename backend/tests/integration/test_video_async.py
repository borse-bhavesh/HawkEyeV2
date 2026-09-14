
import pytest
import asyncio
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import os
import tempfile
import time

from app.main import app
from app.db.database import get_db, SessionLocal
from app.db.models import Base
from app.services.video_processing_status import VideoProcessingStatus

@pytest.fixture(scope="function")
def test_db():
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from sqlalchemy.orm import sessionmaker
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestingSessionLocal
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()

@pytest.fixture
def client(test_db):
    return TestClient(app)

def create_valid_mp4_bytes():
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "test_video.mp4")
    with open(fixture_path, "rb") as f:
        return f.read()

@patch("fastapi.BackgroundTasks.add_task")
def test_upload_returns_before_processing_and_temp_file_lifetime(mock_add_task, client):
    file_bytes = create_valid_mp4_bytes()

    response = client.post(
        "/api/v1/video/upload",
        files={"file": ("test_video.mp4", file_bytes, "video/mp4")},
        params={"max_frames": 3}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] is not None
    assert data["status"].upper() == "UPLOADED"

    mock_add_task.assert_not_called()

@patch("app.api.video.VideoProcessingService.process")
@patch("fastapi.BackgroundTasks.add_task")
@patch("app.api.video.SessionLocal")
def test_background_task_creates_fresh_db_session(mock_session_local, mock_add_task, mock_process, client, test_db):
    mock_session_local.side_effect = test_db
    file_bytes = create_valid_mp4_bytes()

    response = client.post(
        "/api/v1/video/upload",
        files={"file": ("test_video.mp4", file_bytes, "video/mp4")},
    )
    session_id = response.json()["session_id"]
    
    # Save zone
    zone_resp = client.put(f"/api/v1/sessions/{session_id}/zone", json={"polygon": [{"x":0,"y":0},{"x":1,"y":1},{"x":1,"y":0}]})
    assert zone_resp.status_code == 200
    
    # Verify zone is persisted
    get_resp = client.get(f"/api/v1/sessions/{session_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["restricted_zone"] is not None
    
    # Analyze
    analyze_resp = client.post(f"/api/v1/sessions/{session_id}/analyze")
    assert analyze_resp.status_code == 200
    
    mock_add_task.assert_called_once()
    task_func = mock_add_task.call_args[0][0]
    
    
    from app.api.video import _run_async_processing_pipeline
    _run_async_processing_pipeline(session_id, "dummy_path", "test_video.mp4", detector=MagicMock(), zone_data=None)
    
    mock_process.assert_called_once()

@patch("fastapi.BackgroundTasks.add_task")
def test_repeated_uploads(mock_add_task, client):
    file_bytes = create_valid_mp4_bytes()

    session_ids = set()
    for _ in range(3):
        response = client.post(
            "/api/v1/video/upload",
            files={"file": ("test_video.mp4", file_bytes, "video/mp4")},
        )
        assert response.status_code == 200
        d = response.json()
        assert d["status"].upper() == "UPLOADED"
        session_ids.add(d["session_id"])
        
    assert len(session_ids) == 3
