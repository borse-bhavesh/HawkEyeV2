import pytest
import uuid
import os
import shutil
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal
from app.db.models import (
    ProcessingSession, Track, TrackObservation, Event, 
    RiskAssessment, Evidence, risk_assessment_events
)
from sqlalchemy import delete
from app.services.events.models import EventType
from app.services.risk.models import RiskLevel, Priority, RiskAssessmentStatus
from app.services.evidence.models import EvidenceType
from app.core.config import settings

client = TestClient(app)

@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def setup_test_session(db, session_id, status="COMPLETED"):
    # Insert session
    sess = ProcessingSession(
        session_id=session_id,
        source_id="test_source",
        source_type="test_type",
        status=status,
        created_at="2026-01-01T00:00:00Z"
    )
    db.add(sess)
    
    # Insert track
    track_id = str(uuid.uuid4())
    track = Track(
        id=track_id,
        processing_session_id=session_id,
        session_track_id=1,
        class_id=0,
        class_name="person",
        confidence=0.9,
        latest_bbox={"x1": 0, "y1": 0, "x2": 10, "y2": 10}
    )
    db.add(track)
    
    # Insert observation
    obs = TrackObservation(
        processing_session_id=session_id,
        track_id=track_id,
        frame_number=1,
        timestamp_seconds=0.1,
        class_name="person",
        confidence=0.9,
        bbox_x1=0, bbox_y1=0, bbox_x2=10, bbox_y2=10
    )
    db.add(obs)
    
    # Insert event
    event_id = str(uuid.uuid4())
    evt = Event(
        event_id=event_id,
        processing_session_id=session_id,
        event_type=EventType.ZONE_ENTRY.name,
        frame_number=1,
        timestamp_seconds=0.1,
        description="test event",
        track_id=track_id
    )
    db.add(evt)
    
    # Insert risk
    risk_id = str(uuid.uuid4())
    risk = RiskAssessment(
        assessment_id=risk_id,
        processing_session_id=session_id,
        risk_level=RiskLevel.HIGH.name,
        priority=Priority.HIGH.name,
        status=RiskAssessmentStatus.OPEN.name,
        reason="test risk"
    )
    db.add(risk)
    db.flush()
    
    # Link event and risk
    db.execute(risk_assessment_events.insert().values(assessment_id=risk_id, event_id=event_id))
    
    # Insert evidence
    evidence_id = str(uuid.uuid4())
    evid = Evidence(
        evidence_id=evidence_id,
        processing_session_id=session_id,
        evidence_type=EvidenceType.FRAME.name,
        source_id="src",
        source_type="src",
        event_id=event_id
    )
    db.add(evid)
    
    db.commit()
    
    # Create media directory
    media_dir = Path(settings.media_root).resolve() / "sessions" / session_id
    media_dir.mkdir(parents=True, exist_ok=True)
    (media_dir / "source.mp4").touch()
    
    return session_id, track_id, event_id, risk_id, evidence_id, media_dir


def test_delete_existing_session(db):
    session_id = str(uuid.uuid4())
    ids = setup_test_session(db, session_id)
    session_id, track_id, event_id, risk_id, evidence_id, media_dir = ids
    
    response = client.delete(f"/api/v1/sessions/{session_id}")
    assert response.status_code == 204
    
    # Verify DB
    assert db.query(ProcessingSession).filter_by(session_id=session_id).first() is None
    assert db.query(Track).filter_by(processing_session_id=session_id).first() is None
    assert db.query(TrackObservation).filter_by(processing_session_id=session_id).first() is None
    assert db.query(Event).filter_by(processing_session_id=session_id).first() is None
    assert db.query(RiskAssessment).filter_by(processing_session_id=session_id).first() is None
    assert db.query(Evidence).filter_by(processing_session_id=session_id).first() is None
    
    # Verify association table is cleared via cascade automatically
    # (By checking no links exist for this event or risk)
    res = db.execute(risk_assessment_events.select().where(risk_assessment_events.c.assessment_id == risk_id)).fetchall()
    assert len(res) == 0
    
    # Verify Media
    assert not media_dir.exists()
    assert not Path(str(media_dir) + ".deleted").exists()

def test_delete_nonexistent_session():
    session_id = str(uuid.uuid4())
    response = client.delete(f"/api/v1/sessions/{session_id}")
    assert response.status_code == 404

def test_delete_invalid_uuid():
    response = client.delete(f"/api/v1/sessions/invalid-uuid")
    assert response.status_code == 400

def test_delete_active_session_started(db):
    session_id = str(uuid.uuid4())
    ids = setup_test_session(db, session_id, status="STARTED")
    session_id, track_id, event_id, risk_id, evidence_id, media_dir = ids
    
    response = client.delete(f"/api/v1/sessions/{session_id}")
    assert response.status_code == 409
    
    # Verify DB and Media intact
    assert db.query(ProcessingSession).filter_by(session_id=session_id).first() is not None
    assert media_dir.exists()
    
    # Cleanup manual
    db.execute(delete(TrackObservation).where(TrackObservation.processing_session_id == session_id))
    sess = db.query(ProcessingSession).filter_by(session_id=session_id).first()
    if sess:
        db.delete(sess)
    db.commit()
    shutil.rmtree(media_dir, ignore_errors=True)

def test_delete_active_session_processing(db):
    session_id = str(uuid.uuid4())
    ids = setup_test_session(db, session_id, status="PROCESSING")
    session_id, track_id, event_id, risk_id, evidence_id, media_dir = ids
    
    response = client.delete(f"/api/v1/sessions/{session_id}")
    assert response.status_code == 409
    
    # Verify DB and Media intact
    assert db.query(ProcessingSession).filter_by(session_id=session_id).first() is not None
    assert media_dir.exists()
    
    # Cleanup manual
    db.execute(delete(TrackObservation).where(TrackObservation.processing_session_id == session_id))
    sess = db.query(ProcessingSession).filter_by(session_id=session_id).first()
    if sess:
        db.delete(sess)
    db.commit()
    shutil.rmtree(media_dir, ignore_errors=True)

def test_delete_one_does_not_affect_another(db):
    session_id_a = str(uuid.uuid4())
    ids_a = setup_test_session(db, session_id_a, status="FAILED")
    
    session_id_b = str(uuid.uuid4())
    ids_b = setup_test_session(db, session_id_b, status="COMPLETED")
    
    response = client.delete(f"/api/v1/sessions/{session_id_a}")
    assert response.status_code == 204
    
    # Verify A is gone
    assert db.query(ProcessingSession).filter_by(session_id=session_id_a).first() is None
    assert not ids_a[5].exists()
    
    # Verify B is intact
    assert db.query(ProcessingSession).filter_by(session_id=session_id_b).first() is not None
    assert db.query(TrackObservation).filter_by(processing_session_id=session_id_b).first() is not None
    assert ids_b[5].exists()
    
    # Cleanup manual for B
    db.execute(delete(TrackObservation).where(TrackObservation.processing_session_id == session_id_b))
    sess = db.query(ProcessingSession).filter_by(session_id=session_id_b).first()
    if sess:
        db.delete(sess)
    db.commit()
    shutil.rmtree(ids_b[5], ignore_errors=True)

def test_delete_missing_media_safe(db):
    session_id = str(uuid.uuid4())
    ids = setup_test_session(db, session_id, status="UPLOADED")
    session_id, track_id, event_id, risk_id, evidence_id, media_dir = ids
    
    # Manually remove media before API call
    shutil.rmtree(media_dir, ignore_errors=True)
    
    response = client.delete(f"/api/v1/sessions/{session_id}")
    assert response.status_code == 204
    
    # Verify DB is still cleaned
    assert db.query(ProcessingSession).filter_by(session_id=session_id).first() is None
