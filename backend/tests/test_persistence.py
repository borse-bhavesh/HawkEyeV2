import pytest
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.repositories.domain import ProcessingSessionDomain, TrackDomain
from app.services.events.models import Event as DomainEvent, EventType
from app.services.risk.models import RiskAssessment as DomainRiskAssessment, RiskLevel, Priority, RiskAssessmentStatus

from app.repositories.sql_repo import (
    SQLProcessingSessionRepository,
    SQLTrackRepository,
    SQLEventRepository,
    SQLRiskAssessmentRepository
)
from app.services.persistence.core import CorePersistenceService

TEST_DB_URL = "postgresql+psycopg://hawkeye:hawkeye@localhost:5432/hawkeye_test"

@pytest.fixture(scope="module")
def engine():
    eng = create_engine(TEST_DB_URL)
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
def persistence_service(db_session):
    return CorePersistenceService(
        session_repo=SQLProcessingSessionRepository(db_session),
        track_repo=SQLTrackRepository(db_session),
        event_repo=SQLEventRepository(db_session),
        risk_repo=SQLRiskAssessmentRepository(db_session)
    )


def test_persistence_service_processing_session(persistence_service, db_session):
    session_id = "test_persistence_session_1"
    sess = ProcessingSessionDomain(
        session_id=session_id,
        source_id="cam_1",
        source_type="RTSP",
        created_at=datetime.now(timezone.utc)
    )
    
    # Save
    persistence_service.save_processing_session(sess)
    db_session.commit()
    
    # Retrieve
    retrieved = persistence_service.get_processing_session(session_id)
    assert retrieved is not None
    assert retrieved.session_id == session_id
    
    # Update
    sess.status = "COMPLETED"
    persistence_service.update_processing_session(sess)
    db_session.commit()
    
    retrieved_updated = persistence_service.get_processing_session(session_id)
    assert retrieved_updated.status == "COMPLETED"
    
    # Missing ID
    assert persistence_service.get_processing_session("missing") is None


def test_persistence_service_track(persistence_service, db_session):
    session_id = "test_persistence_session_2"
    sess = ProcessingSessionDomain(
        session_id=session_id, source_id="cam_1", source_type="RTSP", created_at=datetime.now(timezone.utc)
    )
    persistence_service.save_processing_session(sess)
    
    track_id = "track_persistence_1"
    track = TrackDomain(
        id=track_id, processing_session_id=session_id, session_track_id=1, class_name="person"
    )
    persistence_service.save_track(track)
    db_session.commit()
    
    # Retrieve
    retrieved = persistence_service.get_track(track_id)
    assert retrieved is not None
    assert retrieved.class_name == "person"
    
    # Retrieve by session
    tracks = persistence_service.get_session_tracks(session_id)
    assert len(tracks) == 1
    assert tracks[0].id == track_id


def test_persistence_service_event_and_risk(persistence_service, db_session):
    session_id = "test_persistence_session_3"
    sess = ProcessingSessionDomain(
        session_id=session_id, source_id="cam_1", source_type="RTSP", created_at=datetime.now(timezone.utc)
    )
    persistence_service.save_processing_session(sess)
    
    # Track
    track_id = "track_persistence_2"
    track = TrackDomain(id=track_id, processing_session_id=session_id, session_track_id=1)
    persistence_service.save_track(track)
    
    # Event
    event_id = "evt_persistence_1"
    evt = DomainEvent(
        event_id=event_id,
        event_type=EventType.LOITERING,
        frame_number=100,
        timestamp_seconds=5.0,
        description="Person loitering",
        track_id=None,
        evidence={"duration": 15.0}
    )
    persistence_service.save_event(evt, session_id)
    
    # Risk
    assessment_id = "risk_persistence_1"
    risk = DomainRiskAssessment(
        event_id=assessment_id,
        contributing_event_ids=[event_id],
        contributing_event_types=[EventType.LOITERING],
        risk_level=RiskLevel.HIGH,
        priority=Priority.HIGH,
        reason="Loitering detected",
        status=RiskAssessmentStatus.OPEN
    )
    persistence_service.save_risk_assessment(risk, session_id)
    
    # Commit transaction
    db_session.commit()
    
    # Retrieve and verify event
    retrieved_evt = persistence_service.get_event(event_id)
    assert retrieved_evt is not None
    assert retrieved_evt.event_type == EventType.LOITERING
    
    # Retrieve and verify risk assessment
    retrieved_risk = persistence_service.get_risk_assessment(assessment_id)
    assert retrieved_risk is not None
    assert retrieved_risk.risk_level == RiskLevel.HIGH
    assert event_id in retrieved_risk.contributing_event_ids
    assert len(retrieved_risk.contributing_event_ids) == 1


def test_transaction_rollback_behavior(persistence_service, db_session):
    session_id = "test_persistence_rollback"
    sess = ProcessingSessionDomain(
        session_id=session_id, source_id="cam_1", source_type="RTSP", created_at=datetime.now(timezone.utc)
    )
    persistence_service.save_processing_session(sess)
    
    # Implicit transaction rollback because of the fixture yield pattern if not committed explicitly
    db_session.rollback()
    
    assert persistence_service.get_processing_session(session_id) is None


def test_domain_separation(persistence_service, db_session):
    session_id = "test_persistence_sep"
    sess = ProcessingSessionDomain(
        session_id=session_id, source_id="cam_1", source_type="RTSP", created_at=datetime.now(timezone.utc)
    )
    persistence_service.save_processing_session(sess)
    db_session.commit()
    
    retrieved = persistence_service.get_processing_session(session_id)
    
    # We should not leak SQL model objects, it should be the domain model.
    assert isinstance(retrieved, ProcessingSessionDomain)
    assert not hasattr(retrieved, "__tablename__")
