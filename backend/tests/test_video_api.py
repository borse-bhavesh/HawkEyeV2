from pathlib import Path
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.database import get_db
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

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_test_db():
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


client = TestClient(app)

TEST_VIDEO = (
    Path(__file__).parent
    / "fixtures"
    / "test_video.mp4"
)


def test_video_metadata_endpoint():
    response = client.get(
        "/api/v1/video/metadata",
        params={
            "source": str(TEST_VIDEO),
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["source"] == str(TEST_VIDEO)
    assert data["fps"] > 0
    assert data["frame_count"] > 0
    assert data["width"] == 1280
    assert data["height"] == 720
    assert data["duration_seconds"] > 0


def test_video_metadata_missing_source():
    response = client.get(
        "/api/v1/video/metadata",
        params={
            "source": str(
                Path(__file__).parent
                / "fixtures"
                / "does_not_exist.mp4"
            ),
        },
    )

    assert response.status_code == 404

    data = response.json()

    assert data["detail"] == "Video source not found."

def test_video_process_endpoint():
    response = client.get(
        "/api/v1/video/process",
        params={
            "source": str(TEST_VIDEO),
            "max_frames": 10,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["source"] == str(TEST_VIDEO)
    assert data["frames_processed"] == 10
    assert data["first_frame_number"] == 1
    assert data["last_frame_number"] == 10
    assert data["total_frames_read"] == 10
    assert data["frames_skipped"] == 0


def test_video_process_invalid_max_frames():
    response = client.get(
        "/api/v1/video/process",
        params={
            "source": str(TEST_VIDEO),
            "max_frames": 0,
        },
    )

    assert response.status_code == 400

    data = response.json()

    assert data["detail"] == "max_frames must be greater than 0."

def test_video_process_with_frame_skip():
    response = client.get(
        "/api/v1/video/process",
        params={
            "source": str(TEST_VIDEO),
            "max_frames": 5,
            "frame_skip": 1,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["source"] == str(TEST_VIDEO)
    assert data["frames_processed"] == 5
    assert data["first_frame_number"] == 1
    assert data["last_frame_number"] == 9
    assert data["total_frames_read"] == 9
    assert data["frames_skipped"] == 4

def test_video_process_invalid_frame_skip():
    response = client.get(
        "/api/v1/video/process",
        params={
            "source": str(TEST_VIDEO),
            "max_frames": 5,
            "frame_skip": -1,
        },
    )

    assert response.status_code == 400

    data = response.json()

    assert (
        data["detail"]
        == "frame_skip must be greater than or equal to 0."
    )