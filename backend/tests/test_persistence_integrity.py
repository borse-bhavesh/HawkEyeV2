import pytest
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, DataError

from app.db.models import Base, ProcessingSession, Track, Event, RiskAssessment, Evidence as SQLEvidence
from app.repositories.domain import ProcessingSessionDomain, TrackDomain
from app.services.events.models import Event as DomainEvent, EventType
from app.services.risk.models import RiskAssessment as DomainRiskAssessment, RiskLevel, Priority, RiskAssessmentStatus
from app.services.evidence.models import Evidence, EvidenceType, EvidenceSource, FrameEvidence, VideoSegmentEvidence

from app.repositories.sql_repo import (
    SQLProcessingSessionRepository,
    SQLTrackRepository,
    SQLEventRepository,
    SQLRiskAssessmentRepository,
    SQLEvidenceRepository
)
from app.repositories.exceptions import DuplicateRecordError
from app.services.evidence.lifecycle import EvidenceLifecycleService
from app.services.persistence.core import CorePersistenceService
from app.services.persistence.evidence import EvidencePersistenceService
from app.services.persistence.orchestrator import ProcessingPersistenceOrchestrator
from app.services.persistence.history import HistoryService

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
def architecture(db_session):
    core = CorePersistenceService(
        session_repo=SQLProcessingSessionRepository(db_session),
        track_repo=SQLTrackRepository(db_session),
        event_repo=SQLEventRepository(db_session),
        risk_repo=SQLRiskAssessmentRepository(db_session)
    )
    evidence = EvidencePersistenceService(
        evidence_repo=SQLEvidenceRepository(db_session),
        lifecycle_service=EvidenceLifecycleService()
    )
    orchestrator = ProcessingPersistenceOrchestrator(core, evidence)
    history = HistoryService(core, evidence)
    return {
        "core": core,
        "evidence": evidence,
        "orchestrator": orchestrator,
        "history": history
    }


def test_foreign_key_and_failure_isolation(architecture, db_session):
    """
    PART B & PART I & PART G: Foreign Key Integrity, Failure Isolation, Session Reuse.
    """
    orch = architecture["orchestrator"]
    history = architecture["history"]

    # 1. Start a session
    session_id = "test_integrity_session_1"
    session = orch.start_session(session_id, "cam_1", "RTSP")
    db_session.commit()
    
    # 2. Add valid Track & Event
    track = TrackDomain(id="track_valid", processing_session_id=session_id, session_track_id=1)
    event = DomainEvent(event_id="evt_valid", event_type=EventType.LOITERING, frame_number=10, timestamp_seconds=1.0, description="desc")
    
    # 3. Add RiskAssessment with INVALID contributing event
    risk = DomainRiskAssessment(
        event_id="risk_fk_fail",
        contributing_event_ids=["nonexistent_event_id"], 
        contributing_event_types=[],
        risk_level=RiskLevel.HIGH,
        priority=Priority.HIGH,
        reason="desc",
        status=RiskAssessmentStatus.OPEN
    )

    # 4. Attempt to save all
    with pytest.raises(Exception):
        orch.complete_session(session, [track], [], [event], [risk], [])
        db_session.flush() # Force SQL execution of the risk association
        
    # 5. Rollback
    db_session.rollback()
    
    # 6. Verify nothing from the failed transaction persisted
    historical = history.get_historical_run(session_id)
    assert len(historical.tracks) == 0
    assert len(historical.events) == 0
    assert len(historical.risk_assessments) == 0
    
    # 7. Session reuse: We can now save successfully in the same SQLAlchemy session
    orch.complete_session(session, [track], [], [event], [], [])
    db_session.commit()
    
    historical2 = history.get_historical_run(session_id)
    assert len(historical2.tracks) == 1
    assert len(historical2.events) == 1


def test_duplicate_handling(architecture, db_session):
    """
    PART E: Constraint / Duplicate Handling.
    """
    core = architecture["core"]
    
    session = ProcessingSessionDomain(session_id="dup_sess", source_id="cam_1", source_type="RTSP", created_at=datetime.now(timezone.utc))
    core.save_processing_session(session)
    db_session.commit()

    track1 = TrackDomain(id="track_dup", processing_session_id="dup_sess", session_track_id=1)
    core.save_track(track1)
    db_session.commit()
    
    track2 = TrackDomain(id="track_dup", processing_session_id="dup_sess", session_track_id=2)
    
    # Duplicate ID now triggers an UPSERT, not DuplicateRecordError
    core.save_track(track2)
    db_session.commit()
        
    retrieved = core.get_track("track_dup")
    assert retrieved.session_track_id == 1


def test_enum_integrity_rejection(db_session):
    """
    PART D: Enum Integrity.
    """
    # Create session
    db_session.execute(text("INSERT INTO processing_sessions (session_id, source_id, source_type, created_at, status) VALUES ('enum_sess', 'cam_1', 'RTSP', NOW(), 'STARTED')"))
    db_session.commit()
    
    # Try inserting raw invalid enum via SQLAlchemy
    # The database itself should reject it because of PostgreSQL ENUM types
    with pytest.raises(DataError):
        db_session.execute(text("INSERT INTO events (event_id, processing_session_id, event_type, frame_number, timestamp_seconds, description) VALUES ('enum_evt', 'enum_sess', 'INVALID_ENUM_VALUE', 1, 1.0, 'desc')"))
        
    db_session.rollback()


def test_historical_isolation(architecture, db_session):
    """
    PART J: Historical Consistency (Isolation between sessions).
    """
    orch = architecture["orchestrator"]
    history = architecture["history"]

    sess1 = orch.start_session("iso_sess_1", "cam_1", "RTSP")
    sess2 = orch.start_session("iso_sess_2", "cam_2", "RTSP")
    db_session.commit()

    # Populate Session 1
    t1 = TrackDomain(id="t1", processing_session_id="iso_sess_1", session_track_id=1)
    e1 = DomainEvent(event_id="e1", event_type=EventType.LOITERING, frame_number=1, timestamp_seconds=1.0, description="desc")
    orch.complete_session(sess1, [t1], [], [e1], [], [])
    
    # Populate Session 2
    t2 = TrackDomain(id="t2", processing_session_id="iso_sess_2", session_track_id=1)
    e2 = DomainEvent(event_id="e2", event_type=EventType.ZONE_ENTRY, frame_number=2, timestamp_seconds=2.0, description="desc")
    orch.complete_session(sess2, [t2], [], [e2], [], [])
    
    db_session.commit()
    
    h1 = history.get_historical_run("iso_sess_1")
    assert len(h1.tracks) == 1
    assert h1.tracks[0].id == "t1"
    assert len(h1.events) == 1
    assert h1.events[0].event_id == "e1"

    h2 = history.get_historical_run("iso_sess_2")
    assert len(h2.tracks) == 1
    assert h2.tracks[0].id == "t2"
    assert len(h2.events) == 1
    assert h2.events[0].event_id == "e2"


def test_comprehensive_end_to_end(architecture, db_session):
    """
    PART O: Comprehensive End-to-End processing run.
    PART K: Domain/ORM Separation.
    PART L: Evidence Integrity (Metadata only).
    """
    orch = architecture["orchestrator"]
    history = architecture["history"]

    session_id = "comprehensive_run_1"
    session = orch.start_session(session_id, "cam_1", "RTSP")
    
    # 2 Tracks
    t1 = TrackDomain(id="comp_t1", processing_session_id=session_id, session_track_id=1, class_name="person")
    t2 = TrackDomain(id="comp_t2", processing_session_id=session_id, session_track_id=2, class_name="vehicle")
    
    # 2 Events
    e1 = DomainEvent(event_id="comp_e1", event_type=EventType.LOITERING, frame_number=10, timestamp_seconds=1.0, description="Person loitering", track_id=1, evidence={"zone": "A"})
    e2 = DomainEvent(event_id="comp_e2", event_type=EventType.ZONE_ENTRY, frame_number=20, timestamp_seconds=2.0, description="Vehicle entered", track_id=2)
    
    # 1 Risk Assessment associating both events
    risk = DomainRiskAssessment(
        event_id="comp_r1",
        contributing_event_ids=["comp_e1", "comp_e2"],
        contributing_event_types=[EventType.LOITERING, EventType.ZONE_ENTRY],
        risk_level=RiskLevel.HIGH,
        priority=Priority.CRITICAL,
        reason="Multiple security triggers",
        status=RiskAssessmentStatus.OPEN
    )
    
    # 2 Evidence Items
    ev_frame = Evidence(
        evidence_id="comp_ev_frame",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam_1", source_type="RTSP"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.0),
        event_id="comp_e1"
    )
    
    ev_seg = Evidence(
        evidence_id="comp_ev_seg",
        evidence_type=EvidenceType.VIDEO_SEGMENT,
        source=EvidenceSource(source_id="cam_1", source_type="RTSP"),
        video_segment=VideoSegmentEvidence(start_frame_number=1, end_frame_number=30, start_timestamp_seconds=0.0, end_timestamp_seconds=3.0),
        assessment_id="comp_r1"
    )
    
    # Complete
    orch.complete_session(session, [t1, t2], [], [e1, e2], [risk], [ev_frame, ev_seg])
    db_session.commit()
    
    # History Retrieval
    h = history.get_historical_run(session_id)
    
    assert len(h.tracks) == 2
    assert len(h.events) == 2
    assert len(h.risk_assessments) == 1
    assert len(h.evidence) == 2
    
    r1 = h.risk_assessments[0]
    assert len(r1.contributing_event_ids) == 2
    assert "comp_e1" in r1.contributing_event_ids
    assert "comp_e2" in r1.contributing_event_ids
    
    # Domain Separation & Metadata
    for e in h.evidence:
        assert isinstance(e, Evidence)
        assert not hasattr(e, "__tablename__")
        assert not hasattr(e, "image_bytes")
        assert not hasattr(e, "video_bytes")
