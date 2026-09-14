import pytest
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.db.models import Base
from app.repositories.domain import ProcessingSessionDomain
from app.services.events.models import Event as DomainEvent, EventType
from app.services.risk.models import RiskAssessment as DomainRiskAssessment, RiskLevel, Priority, RiskAssessmentStatus
from app.services.evidence.models import Evidence, EvidenceType, EvidenceSource, FrameEvidence, VideoSegmentEvidence

from app.repositories.sql_repo import (
    SQLProcessingSessionRepository,
    SQLEventRepository,
    SQLRiskAssessmentRepository,
    SQLEvidenceRepository
)
from app.services.evidence.lifecycle import EvidenceLifecycleService
from app.services.persistence.evidence import EvidencePersistenceService

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
def repo_setup(db_session):
    return {
        "session_repo": SQLProcessingSessionRepository(db_session),
        "event_repo": SQLEventRepository(db_session),
        "risk_repo": SQLRiskAssessmentRepository(db_session),
        "evidence_repo": SQLEvidenceRepository(db_session)
    }


@pytest.fixture
def evidence_service(repo_setup):
    return EvidencePersistenceService(
        evidence_repo=repo_setup["evidence_repo"],
        lifecycle_service=EvidenceLifecycleService()
    )


def test_frame_evidence_persistence_and_relationships(evidence_service, repo_setup, db_session):
    # Setup dependencies
    session_id = "test_ev_session_1"
    repo_setup["session_repo"].save(ProcessingSessionDomain(session_id=session_id, source_id="cam_1", source_type="RTSP", created_at=datetime.now(timezone.utc)))
    
    event_id = "test_ev_event_1"
    evt = DomainEvent(event_id=event_id, event_type=EventType.LOITERING, frame_number=10, timestamp_seconds=1.0, description="desc")
    repo_setup["event_repo"].save(evt, session_id)
    
    db_session.commit()

    # Frame Evidence
    evidence_id = "frame_ev_1"
    ev = Evidence(
        evidence_id=evidence_id,
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam_1", source_type="RTSP"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.0),
        event_id=event_id,
        assessment_id=None
    )
    
    evidence_service.save_evidence(ev, session_id)
    db_session.commit()
    
    # Retrieval
    retrieved = evidence_service.get_evidence(evidence_id)
    assert retrieved is not None
    assert retrieved.evidence_id == evidence_id
    assert retrieved.evidence_type == EvidenceType.FRAME
    assert retrieved.frame is not None
    assert retrieved.frame.frame_number == 10
    assert retrieved.source.source_id == "cam_1"
    
    # Event Relationship
    event_evidence = evidence_service.get_event_evidence(event_id)
    assert len(event_evidence) == 1
    assert event_evidence[0].evidence_id == evidence_id
    
    # Session Relationship
    session_evidence = evidence_service.get_session_evidence(session_id)
    assert len(session_evidence) == 1


def test_video_segment_evidence_persistence_and_risk(evidence_service, repo_setup, db_session):
    session_id = "test_ev_session_2"
    repo_setup["session_repo"].save(ProcessingSessionDomain(session_id=session_id, source_id="cam_1", source_type="RTSP", created_at=datetime.now(timezone.utc)))
    
    assessment_id = "test_ev_risk_1"
    risk = DomainRiskAssessment(
        event_id=assessment_id,
        contributing_event_ids=[],
        contributing_event_types=[],
        risk_level=RiskLevel.HIGH,
        priority=Priority.HIGH,
        reason="desc",
        status=RiskAssessmentStatus.OPEN
    )
    repo_setup["risk_repo"].save(risk, session_id)
    
    db_session.commit()

    evidence_id = "segment_ev_1"
    ev = Evidence(
        evidence_id=evidence_id,
        evidence_type=EvidenceType.VIDEO_SEGMENT,
        source=EvidenceSource(source_id="cam_1", source_type="RTSP"),
        video_segment=VideoSegmentEvidence(start_frame_number=1, end_frame_number=100, start_timestamp_seconds=0.0, end_timestamp_seconds=10.0),
        event_id=None,
        assessment_id=assessment_id
    )
    
    evidence_service.save_evidence(ev, session_id)
    db_session.commit()
    
    retrieved = evidence_service.get_evidence(evidence_id)
    assert retrieved is not None
    assert retrieved.video_segment.end_frame_number == 100
    
    assessment_evidence = evidence_service.get_assessment_evidence(assessment_id)
    assert len(assessment_evidence) == 1
    assert assessment_evidence[0].evidence_id == evidence_id


def test_invalid_foreign_key_behavior(evidence_service, repo_setup, db_session):
    evidence_id = "invalid_ev_1"
    ev = Evidence(
        evidence_id=evidence_id,
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam_1", source_type="RTSP"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.0),
        event_id="non_existent_event"
    )
    
    with pytest.raises(Exception):
        # The SQL layer should reject this because the event does not exist.
        # It's an IntegrityError translated to DuplicateRecordError or similar by repo
        evidence_service.save_evidence(ev, session_id="some_session")


def test_domain_separation_and_no_raw_media(evidence_service, repo_setup, db_session):
    session_id = "test_ev_session_3"
    repo_setup["session_repo"].save(ProcessingSessionDomain(session_id=session_id, source_id="cam_1", source_type="RTSP", created_at=datetime.now(timezone.utc)))
    
    event_id = "test_ev_event_3"
    evt = DomainEvent(event_id=event_id, event_type=EventType.LOITERING, frame_number=10, timestamp_seconds=1.0, description="desc")
    repo_setup["event_repo"].save(evt, session_id)
    db_session.commit()
    
    evidence_id = "frame_ev_3"
    ev = Evidence(
        evidence_id=evidence_id,
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam_1", source_type="RTSP"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.0),
        event_id=event_id
    )
    evidence_service.save_evidence(ev, session_id)
    db_session.commit()
    
    retrieved = evidence_service.get_evidence(evidence_id)
    
    # 1. Domain Separation
    assert isinstance(retrieved, Evidence)
    assert not hasattr(retrieved, "__tablename__")
    
    # 2. No Raw Media
    assert not hasattr(retrieved, "image_bytes")
    assert not hasattr(retrieved, "video_bytes")
    assert not hasattr(retrieved, "raw_data")
    assert not hasattr(retrieved, "numpy_array")


from pydantic import ValidationError

def test_validation_rejects_invalid_evidence(evidence_service):
    evidence_id = "invalid_ev_2"
    with pytest.raises(ValidationError):
        ev = Evidence(
            evidence_id=evidence_id,
            evidence_type=EvidenceType.FRAME,
            source=EvidenceSource(source_id="cam_1", source_type="RTSP"),
            # Mismatch: Frame type but provides segment
            video_segment=VideoSegmentEvidence(start_frame_number=1, end_frame_number=100, start_timestamp_seconds=0.0, end_timestamp_seconds=10.0),
            event_id="valid_event"
        )


def test_transaction_rollback_evidence(evidence_service, repo_setup, db_session):
    session_id = "test_ev_session_rollback"
    repo_setup["session_repo"].save(ProcessingSessionDomain(session_id=session_id, source_id="cam_1", source_type="RTSP", created_at=datetime.now(timezone.utc)))
    
    event_id = "test_ev_event_rollback"
    evt = DomainEvent(event_id=event_id, event_type=EventType.LOITERING, frame_number=10, timestamp_seconds=1.0, description="desc")
    repo_setup["event_repo"].save(evt, session_id)
    
    db_session.commit()
    
    evidence_id = "frame_ev_rollback"
    ev = Evidence(
        evidence_id=evidence_id,
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam_1", source_type="RTSP"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.0),
        event_id=event_id
    )
    
    evidence_service.save_evidence(ev, session_id)
    
    # Caller rolls back
    db_session.rollback()
    
    assert evidence_service.get_evidence(evidence_id) is None
