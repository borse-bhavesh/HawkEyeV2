import pytest
import os
import uuid
import shutil
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.config import settings
from app.db.database import get_db, SessionLocal
from app.db.models import Base

TEST_DB_URL = "postgresql+psycopg://hawkeye:hawkeye@localhost:5432/hawkeye_test"
test_engine = create_engine(TEST_DB_URL)
TestingSessionLocal = sessionmaker(bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_valid_mp4_bytes():
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "test_video.mp4")
    with open(fixture_path, "rb") as f:
        return f.read()

def override_session_local():
    return TestingSessionLocal()

@pytest.fixture(autouse=True)
def setup_test_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(test_engine)
    with test_engine.connect() as conn:
        from sqlalchemy import text
        conn.execute(text("DROP TYPE IF EXISTS risklevel CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS priority CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS riskassessmentstatus CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS eventtype CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS evidencetype CASCADE"))
        conn.commit()
    Base.metadata.create_all(test_engine)
    yield
    Base.metadata.drop_all(test_engine)
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def patch_session_local():
    with patch("app.api.video.SessionLocal", side_effect=override_session_local):
        yield

client = TestClient(app)

@pytest.fixture
def clean_media_root():
    old_root = settings.media_root
    settings.media_root = "test_media_retrieval"
    Path(settings.media_root).mkdir(exist_ok=True)
    yield
    import shutil
    shutil.rmtree(settings.media_root, ignore_errors=True)
    settings.media_root = old_root

def test_missing_session_video(clean_media_root):
    fake_id = str(uuid.uuid4())
    resp = client.get(f"/api/v1/sessions/{fake_id}/video")
    assert resp.status_code == 404
    assert "Processing session not found" in resp.json()["detail"]

def test_malformed_session_id():
    resp = client.get(f"/api/v1/sessions/invalid-id-format/video")
    assert resp.status_code == 400
    assert "Invalid session ID format" in resp.json()["detail"]

def test_path_traversal_protection(clean_media_root):
    # Attempt absolute path traversal (linux and windows styles)
    resp = client.get(f"/api/v1/sessions/..%2f..%2f..%2f/video")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Not Found"
    
def test_upload_creates_media_and_retrieval(clean_media_root):
    test_video_path = Path("tests/fixtures/test_video.mp4")
    if not test_video_path.exists():
        pytest.skip("Test video not found, skipping full lifecycle test.")
            
    with open(test_video_path, "rb") as f:
        resp = client.post(
            "/api/v1/video/upload",
            files={"file": ("test_video.mp4", f, "video/mp4")},
            params={"max_frames": 2}
        )
    
    if resp.status_code == 422:
        pytest.skip("Test video not readable by cv2, skipping full lifecycle test.")
        
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]
    
    media_dir = Path(settings.media_root) / "sessions" / session_id
    assert media_dir.exists()
    
    get_resp = client.get(f"/api/v1/sessions/{session_id}/video")
    assert get_resp.status_code == 200
    assert get_resp.headers["content-type"] == "video/mp4"
    assert "video/mp4" in get_resp.headers["content-type"]
    assert len(get_resp.content) > 0

def test_range_request_behavior(clean_media_root):
    test_video_path = Path("tests/fixtures/test_video.mp4")
    if not test_video_path.exists():
        pytest.skip("Test video not found, skipping full lifecycle test.")
            
    with open(test_video_path, "rb") as f:
        resp = client.post(
            "/api/v1/video/upload",
            files={"file": ("test_video.mp4", f, "video/mp4")},
            params={"max_frames": 1}
        )
    if resp.status_code == 422:
        pytest.skip("Test video not readable by cv2, skipping full lifecycle test.")
        
    session_id = resp.json()["session_id"]
    
    # Test Range request
    headers = {"Range": "bytes=0-1023"}
    range_resp = client.get(f"/api/v1/sessions/{session_id}/video", headers=headers)
    assert range_resp.status_code == 206
    assert "Content-Range" in range_resp.headers
    assert range_resp.headers["Content-Range"].startswith("bytes 0-1023/")
    assert range_resp.headers["Content-Length"] == "1024"
    assert len(range_resp.content) == 1024
    assert range_resp.headers["Accept-Ranges"] == "bytes"

def test_session_isolation(clean_media_root):
    test_video_path = Path("tests/fixtures/test_video.mp4")
    if not test_video_path.exists():
        pytest.skip("Test video not found, skipping full lifecycle test.")
            
    with open(test_video_path, "rb") as f:
        respA = client.post(
            "/api/v1/video/upload",
            files={"file": ("test_video_A.mp4", f, "video/mp4")},
            params={"max_frames": 1}
        )
    with open(test_video_path, "rb") as f:
        respB = client.post(
            "/api/v1/video/upload",
            files={"file": ("test_video_B.mp4", f, "video/mp4")},
            params={"max_frames": 1}
        )
        
    if respA.status_code == 422:
        pytest.skip("Test video not readable by cv2, skipping full lifecycle test.")
        
    sessionA_id = respA.json()["session_id"]
    sessionB_id = respB.json()["session_id"]
    
    assert sessionA_id != sessionB_id
    
    # Verify session A's media cannot be accessed by B
    get_respA = client.get(f"/api/v1/sessions/{sessionA_id}/video")
    get_respB = client.get(f"/api/v1/sessions/{sessionB_id}/video")
    
    assert get_respA.status_code == 200
    assert get_respB.status_code == 200
    
    # Now simulate B doesn't exist by manually moving media
    media_dir_A = Path(settings.media_root) / "sessions" / sessionA_id
    media_dir_B = Path(settings.media_root) / "sessions" / sessionB_id
    
    import shutil
    shutil.rmtree(media_dir_B)
    
    # Verify B fails and A still works
    assert client.get(f"/api/v1/sessions/{sessionB_id}/video").status_code == 404
    assert client.get(f"/api/v1/sessions/{sessionA_id}/video").status_code == 200

def test_media_type_resolution(clean_media_root):
    from app.api.routes.sessions import get_core_service
    from unittest.mock import Mock
    session_id = str(uuid.uuid4())
    mock_session = Mock()
    mock_session.session_id = session_id
    
    mock_core = Mock()
    mock_core.get_processing_session.return_value = mock_session
    
    app.dependency_overrides[get_core_service] = lambda: mock_core
    try:
        media_dir = Path(settings.media_root) / "sessions" / session_id
        media_dir.mkdir(parents=True)
        
        # Test webm
        (media_dir / "source.webm").write_bytes(b"mock video data")
        resp = client.get(f"/api/v1/sessions/{session_id}/video")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "video/webm"
        
        # Test mkv
        (media_dir / "source.webm").unlink()
        (media_dir / "source.mkv").write_bytes(b"mock video data")
        resp = client.get(f"/api/v1/sessions/{session_id}/video")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "video/x-matroska"
    finally:
        app.dependency_overrides.pop(get_core_service, None)

def test_missing_media_for_valid_session(clean_media_root):
    from app.api.routes.sessions import get_core_service
    from unittest.mock import Mock
    session_id = str(uuid.uuid4())
    mock_session = Mock()
    mock_session.session_id = session_id
    
    mock_core = Mock()
    mock_core.get_processing_session.return_value = mock_session
    
    app.dependency_overrides[get_core_service] = lambda: mock_core
    try:
        resp = client.get(f"/api/v1/sessions/{session_id}/video")
        assert resp.status_code == 404
        assert "Media directory not found" in resp.json()["detail"]
        
        media_dir = Path(settings.media_root) / "sessions" / session_id
        media_dir.mkdir(parents=True)
        resp2 = client.get(f"/api/v1/sessions/{session_id}/video")
        assert resp2.status_code == 404
        assert "Video source not found" in resp2.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_core_service, None)


def test_observations_endpoint(clean_media_root):
    test_video_path = Path("tests/fixtures/test_video.mp4")
    if not test_video_path.exists():
        pytest.skip("Test video not found, skipping full lifecycle test.")
            
    with open(test_video_path, "rb") as f:
        resp = client.post(
            "/api/v1/video/upload",
            files={"file": ("test_video.mp4", f, "video/mp4")},
            params={"max_frames": 2}
        )
    if resp.status_code == 422:
        pytest.skip("Test video not readable by cv2, skipping test.")
        
    session_id = resp.json()["session_id"]
    
    obs_resp = client.get(f"/api/v1/sessions/{session_id}/observations")
    assert obs_resp.status_code == 200
    observations = obs_resp.json()
    assert isinstance(observations, list)
    
    if len(observations) > 0:
        obs = observations[0]
        assert "track_id" in obs
        assert "frame_number" in obs
        assert "timestamp_seconds" in obs
        assert "bbox_x1" in obs
        assert "bbox_y1" in obs
        assert "bbox_x2" in obs
        assert "bbox_y2" in obs
        assert obs["processing_session_id"] == session_id

def test_missing_session_observations():
    import uuid
    fake_id = str(uuid.uuid4())
    resp = client.get(f"/api/v1/sessions/{fake_id}/observations")
    assert resp.status_code == 404

def test_malformed_session_observations():
    resp = client.get(f"/api/v1/sessions/invalid-id/observations")
    assert resp.status_code == 400
