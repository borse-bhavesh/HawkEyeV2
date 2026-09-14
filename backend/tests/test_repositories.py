import pytest
from datetime import datetime, timezone
import os
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.repositories import (
    ProcessingSessionDomain, TrackDomain, 
    SQLProcessingSessionRepository, SQLTrackRepository,
    SQLEventRepository, SQLRiskAssessmentRepository, SQLEvidenceRepository,
    DuplicateRecordError, RecordNotFoundError
)
from app.services.events.models import Event as DomainEvent, EventType
from app.services.risk.models import RiskAssessment as DomainRiskAssessment, RiskLevel, Priority, RiskAssessmentStatus
from app.services.evidence.models import Evidence as DomainEvidence, EvidenceType, EvidenceSource, FrameEvidence


TEST_DB_URL = "postgresql+psycopg://hawkeye:hawkeye@localhost:5432/hawkeye_test"

from sqlalchemy import text

@pytest.fixture(scope="module")
def engine():
    eng = create_engine(TEST_DB_URL)
    # Drop all and create all for a fresh test database state
    Base.metadata.drop_all(eng)
    
    # We also need to drop custom enums if they persist
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


def test_repository_interfaces_and_imports():
    """Ensure interfaces and implementations can be constructed correctly."""
    from app.repositories.interfaces import IProcessingSessionRepository
    # Check that it's a subclass of the interface
    assert issubclass(SQLProcessingSessionRepository, IProcessingSessionRepository)


def test_processing_session_repository(db_session):
    repo = SQLProcessingSessionRepository(db_session)
    
    # Test Create/Save
    session_id = "test_session_1"
    sess = ProcessingSessionDomain(
        session_id=session_id,
        source_id="cam_1",
        source_type="RTSP",
        created_at=datetime.now(timezone.utc)
    )
    repo.save(sess)
    
    # Transactions are controlled by caller
    db_session.commit()
    
    # Test Duplicate Record
    with pytest.raises(DuplicateRecordError):
        repo.save(sess)
    
    # Test Retrieve by ID
    retrieved = repo.get_by_id(session_id)
    assert retrieved is not None
    assert retrieved.session_id == session_id
    assert retrieved.source_id == "cam_1"
    
    # Test Missing ID
    assert repo.get_by_id("non_existent") is None
    
    # Test Update
    sess.status = "COMPLETED"
    repo.update(sess)
    db_session.commit()
    retrieved_updated = repo.get_by_id(session_id)
    assert retrieved_updated.status == "COMPLETED"


def test_track_repository(db_session):
    # Setup session first
    session_repo = SQLProcessingSessionRepository(db_session)
    session_id = "test_session_2"
    session_repo.save(ProcessingSessionDomain(session_id=session_id, source_id="cam_1", source_type="RTSP", created_at=datetime.now(timezone.utc)))
    db_session.commit()

    repo = SQLTrackRepository(db_session)
    
    track_id = "track_1"
    track = TrackDomain(
        id=track_id,
        processing_session_id=session_id,
        session_track_id=1,
        class_id=0,
        class_name="person",
        confidence=0.95,
        latest_bbox={"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 1.0}
    )
    
    repo.save(track)
    db_session.commit()
    
    # Test Retrieve by ID
    retrieved = repo.get_by_id(track_id)
    assert retrieved is not None
    assert retrieved.class_name == "person"
    assert retrieved.latest_bbox == {"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 1.0}
    
    # Test Retrieve by Session
    tracks = repo.get_by_session_id(session_id)
    assert len(tracks) == 1
    assert tracks[0].id == track_id
    
    # Test Missing ID
    assert repo.get_by_id("non_existent") is None


def test_event_repository(db_session):
    # Setup session
    session_repo = SQLProcessingSessionRepository(db_session)
    session_id = "test_session_3"
    session_repo.save(ProcessingSessionDomain(session_id=session_id, source_id="cam_1", source_type="RTSP", created_at=datetime.now(timezone.utc)))
    
    track_repo = SQLTrackRepository(db_session)
    track_repo.save(TrackDomain(id="track_2", processing_session_id=session_id, session_track_id=1))
    db_session.commit()

    repo = SQLEventRepository(db_session)
    
    event_id = "event_1"
    event = DomainEvent(
        event_id=event_id,
        event_type=EventType.LOITERING,
        frame_number=100,
        timestamp_seconds=5.0,
        description="Person loitering",
        track_id=None,
        evidence={"duration": 15.0}
    )
    
    repo.save(event, session_id=session_id)
    db_session.commit()
    
    retrieved = repo.get_by_id(event_id)
    assert retrieved is not None
    assert retrieved.event_type == EventType.LOITERING
    
    events_in_session = repo.get_by_session_id(session_id)
    assert len(events_in_session) == 1


def test_risk_assessment_repository(db_session):
    session_repo = SQLProcessingSessionRepository(db_session)
    session_id = "test_session_4"
    session_repo.save(ProcessingSessionDomain(session_id=session_id, source_id="cam_1", source_type="RTSP", created_at=datetime.now(timezone.utc)))
    
    event_repo = SQLEventRepository(db_session)
    evt = DomainEvent(event_id="evt_for_risk", event_type=EventType.LOITERING, frame_number=10, timestamp_seconds=1.0, description="desc")
    event_repo.save(evt, session_id)
    db_session.commit()

    repo = SQLRiskAssessmentRepository(db_session)
    
    assessment_id = "risk_1"
    risk = DomainRiskAssessment(
        event_id=assessment_id,  # domain uses event_id for risk_assessment id
        contributing_event_ids=["evt_for_risk"],
        contributing_event_types=[EventType.LOITERING],
        risk_level=RiskLevel.HIGH,
        priority=Priority.HIGH,
        reason="Loitering detected",
        status=RiskAssessmentStatus.OPEN
    )
    
    repo.save(risk, session_id)
    db_session.commit()
    
    retrieved = repo.get_by_id(assessment_id)
    assert retrieved is not None
    assert retrieved.risk_level == RiskLevel.HIGH
    assert "evt_for_risk" in retrieved.contributing_event_ids


def test_evidence_repository(db_session):
    session_repo = SQLProcessingSessionRepository(db_session)
    session_id = "test_session_5"
    session_repo.save(ProcessingSessionDomain(session_id=session_id, source_id="cam_1", source_type="RTSP", created_at=datetime.now(timezone.utc)))
    db_session.commit()

    repo = SQLEvidenceRepository(db_session)
    
    event_repo = SQLEventRepository(db_session)
    evt = DomainEvent(event_id="evt_for_ev", event_type=EventType.LOITERING, frame_number=10, timestamp_seconds=1.0, description="desc")
    event_repo.save(evt, session_id)
    db_session.commit()
    
    evidence_id = "ev_1"
    ev = DomainEvidence(
        evidence_id=evidence_id,
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam_1", source_type="RTSP"),
        frame=FrameEvidence(frame_number=100, timestamp_seconds=5.0),
        event_id="evt_for_ev",
        assessment_id=None
    )
    
    repo.save(ev, session_id)
    db_session.commit()
    
    retrieved = repo.get_by_id(evidence_id)
    assert retrieved is not None
    assert retrieved.frame is not None
    assert retrieved.frame.frame_number == 100
    
    # Verify no raw media is persisted (only metadata)
    assert not hasattr(retrieved, 'image_bytes')
    assert not hasattr(retrieved, 'raw_data')


def test_domain_persistence_separation(db_session):
    """Ensure repository methods do not leak SQLAlchemy model objects."""
    repo = SQLProcessingSessionRepository(db_session)
    session_id = "test_session_6"
    repo.save(ProcessingSessionDomain(session_id=session_id, source_id="cam_1", source_type="RTSP", created_at=datetime.now(timezone.utc)))
    db_session.commit()
    
    retrieved = repo.get_by_id(session_id)
    assert isinstance(retrieved, ProcessingSessionDomain)
    # Assert it is NOT a SQLAlchemy model
    assert not hasattr(retrieved, '__tablename__')


def test_transaction_rollback(db_session):
    """Ensure repository operates within caller transaction boundary and can be rolled back."""
    repo = SQLProcessingSessionRepository(db_session)
    session_id = "test_session_rollback"
    
    repo.save(ProcessingSessionDomain(session_id=session_id, source_id="cam_1", source_type="RTSP", created_at=datetime.now(timezone.utc)))
    # Rollback instead of commit
    db_session.rollback()
    
    # Should not be in database
    retrieved = repo.get_by_id(session_id)
    assert retrieved is None
