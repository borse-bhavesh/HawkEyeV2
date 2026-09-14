import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone
import uuid

from app.main import app
from app.db.database import get_db
from app.db.models import Base
from app.services.events.models import Event, EventType
from app.services.risk.models import RiskAssessment, RiskLevel, Priority, RiskAssessmentStatus
from app.services.evidence.models import Evidence, EvidenceType, EvidenceSource, FrameEvidence
from app.repositories.domain import ProcessingSessionDomain, TrackDomain
from app.repositories.sql_repo import (
    SQLProcessingSessionRepository,
    SQLTrackRepository,
    SQLEventRepository,
    SQLRiskAssessmentRepository,
    SQLEvidenceRepository
)

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

TEST_DB_URL = "postgresql+psycopg://hawkeye:hawkeye@localhost:5432/hawkeye_test"

@pytest.fixture(scope="module")
def api_client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="module")
def engine():
    eng = create_engine(TEST_DB_URL, poolclass=NullPool)
    Base.metadata.drop_all(eng)
    with eng.connect() as conn:
        conn.execute(text("DROP TYPE IF EXISTS risklevel CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS priority CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS riskassessmentstatus CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS eventtype CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS evidencetype CASCADE"))
        conn.commit()
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)

@pytest.fixture
def db_session(engine):
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()

@pytest.fixture
def api_test_data(engine):
    print("\n[DEBUG] api_test_data STARTING", flush=True)
    SessionLocal = sessionmaker(bind=engine)
    
    # Override FastAPI dependencies for testing
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    
    session_id = str(uuid.uuid4())
    track_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    assessment_id = str(uuid.uuid4())
    evidence_id = str(uuid.uuid4())

    now = datetime.now(timezone.utc)
    print("[DEBUG] Opening DB Session", flush=True)

    with SessionLocal() as db_session:
        # 1. Processing Session
        print("[DEBUG] Saving Session", flush=True)
        session_repo = SQLProcessingSessionRepository(db_session)
        session_repo.save(ProcessingSessionDomain(
            session_id=session_id,
            source_id="camera_1",
            source_type="RTSP",
            status="COMPLETED",
            created_at=now,
            started_at=now,
            completed_at=now
        ))

        # 2. Track
        track_repo = SQLTrackRepository(db_session)
        track_repo.save(TrackDomain(
            id=track_id,
            processing_session_id=session_id,
            session_track_id=1,
            class_id=0,
            class_name="person",
            confidence=0.9,
            latest_bbox={"x": 10, "y": 10, "w": 100, "h": 100}
        ))

        # 3. Event
        event_repo = SQLEventRepository(db_session)
        event = Event(
            event_id=event_id,
            event_type=EventType.LOITERING,
            frame_number=10,
            timestamp_seconds=1.5,
            description="Test event",
            track_id=1,
            evidence={}
        )
        event_repo.save(event, session_id)

        # 4. Risk Assessment
        risk_repo = SQLRiskAssessmentRepository(db_session)
        assessment = RiskAssessment(
            event_id=assessment_id,
            contributing_event_ids=[event_id],
            contributing_event_types=["LOITERING"],
            risk_level=RiskLevel.MEDIUM,
            priority=Priority.HIGH,
            reason="Test reason",
            status=RiskAssessmentStatus.OPEN,
            evidence=None
        )
        risk_repo.save(assessment, session_id)

        # 5. Evidence
        evidence_repo = SQLEvidenceRepository(db_session)
        evidence = Evidence(
            evidence_id=evidence_id,
            evidence_type=EvidenceType.FRAME,
            source=EvidenceSource(source_id="camera_1", source_type="RTSP"),
            frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
            video_segment=None,
            event_id=event_id,
            assessment_id=assessment_id
        )
        evidence_repo.save(evidence, session_id)

        db_session.commit()
    
    return {
        "session_id": session_id,
        "track_id": track_id,
        "event_id": event_id,
        "assessment_id": assessment_id,
        "evidence_id": evidence_id
    }

def test_health_endpoint(api_client):
    response = api_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["online", "degraded"]
    assert "version" in data
    assert "service" in data

def test_get_sessions(api_client, api_test_data):
    print("\n[DEBUG] test_get_sessions STARTING", flush=True)
    session_id = api_test_data["session_id"]
    print(f"[DEBUG] session_id from fixture: {session_id}", flush=True)
    
    response = api_client.get("/api/v1/sessions")
    
    print(f"[DEBUG] response received: {response.status_code}", flush=True)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    session_ids = [s["session_id"] for s in data]
    assert session_id in session_ids

    # Verify no SQLAlchemy metadata leaked (e.g. _sa_instance_state)
    assert "_sa_instance_state" not in data[0]
    print("[DEBUG] test_get_sessions DONE", flush=True)

def test_get_session_by_id(api_client, api_test_data):
    session_id = api_test_data["session_id"]
    response = api_client.get(f"/api/v1/sessions/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["status"] == "COMPLETED"

def test_get_session_not_found(api_client):
    response = api_client.get("/api/v1/sessions/invalid-id")
    assert response.status_code == 404

def test_get_session_history(api_client, api_test_data):
    session_id = api_test_data["session_id"]
    response = api_client.get(f"/api/v1/sessions/{session_id}/history")
    assert response.status_code == 200
    data = response.json()

    assert data["session"]["session_id"] == session_id
    assert len(data["tracks"]) == 1
    assert len(data["events"]) == 1
    assert len(data["risk_assessments"]) == 1
    assert len(data["evidence"]) == 1

    # Verify Enums serialize to JSON properly (strings or ints, not objects)
    assert isinstance(data["events"][0]["event_type"], str)
    assert isinstance(data["risk_assessments"][0]["risk_level"], str)
    assert isinstance(data["evidence"][0]["evidence_type"], str)

def test_get_session_history_not_found(api_client):
    response = api_client.get("/api/v1/sessions/invalid-id/history")
    assert response.status_code == 404

def test_get_tracks(api_client, api_test_data):
    session_id = api_test_data["session_id"]
    response = api_client.get(f"/api/v1/sessions/{session_id}/tracks")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["class_name"] == "person"

def test_get_events(api_client, api_test_data):
    session_id = api_test_data["session_id"]
    response = api_client.get(f"/api/v1/sessions/{session_id}/events")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["event_type"] == "LOITERING" or data[0]["event_type"] == "EventType.LOITERING"

def test_get_risks(api_client, api_test_data):
    session_id = api_test_data["session_id"]
    response = api_client.get(f"/api/v1/sessions/{session_id}/risks")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["priority"] == "high" or data[0]["priority"] == "Priority.HIGH"

def test_get_evidence(api_client, api_test_data):
    session_id = api_test_data["session_id"]
    response = api_client.get(f"/api/v1/sessions/{session_id}/evidence")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["evidence_id"] == api_test_data["evidence_id"]

