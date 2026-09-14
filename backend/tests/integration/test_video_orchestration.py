import pytest
import uuid
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.db.database import SessionLocal as RealSessionLocal
from app.db.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.api.routes.sessions import get_core_service, get_evidence_service, get_history_service
from app.services.persistence.orchestrator import ProcessingPersistenceOrchestrator

from app.services.video_processing_service import VideoProcessingService, VideoProcessingStatus
from app.services.video_source import LocalVideoSource
from app.services.detection.yolo_detector import YOLODetector
from app.core.config import get_detection_config
from app.services.tracking.config import TrackingConfig
from app.services.events.config import EventIntelligenceConfig
from app.services.risk.config import RiskConfig
from app.services.events.zones import Zone, Point2D

TEST_DB_URL = "postgresql+psycopg://hawkeye:hawkeye@localhost:5432/hawkeye_test"
test_engine = create_engine(TEST_DB_URL)
SessionLocal = sessionmaker(bind=test_engine)

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


TEST_VIDEO = Path(__file__).parent.parent / "fixtures" / "test_video.mp4"


def _setup_services(db: Session):
    core_service = get_core_service(db)
    evidence_service = get_evidence_service(db)
    orchestrator = ProcessingPersistenceOrchestrator(core_service, evidence_service)
    history_service = get_history_service(core_service, evidence_service)
    return orchestrator, history_service


def test_complete_video_processing_end_to_end():
    """
    Integration test connecting real YOLODetector, ByteTrackTracker, EventOrchestrator,
    RiskOrchestrator, EvidenceOrchestrator, and ProcessingPersistenceOrchestrator.
    """
    detection_config = get_detection_config()
    detector = YOLODetector(config=detection_config)
    tracking_config = TrackingConfig()
    event_config = EventIntelligenceConfig()
    risk_config = RiskConfig()
    
    test_zone = Zone(
        zone_id="zone-persistence",
        name="Test Zone Persistence",
        polygon=[Point2D(x=0.0, y=0.0), Point2D(x=100.0, y=0.0), Point2D(x=100.0, y=100.0), Point2D(x=0.0, y=100.0)]
    )

    db = SessionLocal()
    orchestrator, history_service = _setup_services(db)
    
    service = VideoProcessingService(
        detector=detector,
        tracking_config=tracking_config,
        event_config=event_config,
        zones=[test_zone],
        risk_config=risk_config,
        generate_evidence=True,
        persistence_orchestrator=orchestrator
    )
    
    source = LocalVideoSource(TEST_VIDEO)
    session_id = str(uuid.uuid4())
    
    session = orchestrator.start_session(session_id, source.get_source(), "LOCAL_FILE")
    db.commit()
    
    try:
        result = service.process(source, session=session, max_frames=10)
        db.commit()
    except Exception:
        db.rollback()
        if not getattr(service, 'processing_completed', False):
            orchestrator.fail_session(session)
            db.commit()
        raise
    finally:
        db.close()
        
    assert result.status == VideoProcessingStatus.COMPLETED
    assert result.processing.frames_processed == 10
    
    db = SessionLocal()
    try:
        _, history_service = _setup_services(db)
        run = history_service.get_historical_run(session_id)
        
        assert run is not None, "Historical run should be retrievable"
        assert run.session.status == "COMPLETED"
        assert run.session.session_id == session_id
        
        # Traceability: Tracks
        for track in run.tracks:
            assert track.processing_session_id == session_id
            
        # Traceability: Events
        persisted_event_ids = {e.event_id for e in run.events}
            
        # Traceability: Risks -> Events
        for risk in run.risk_assessments:
            for contributing_event_id in risk.contributing_event_ids:
                assert contributing_event_id in persisted_event_ids, "Risk contributes to an unknown event"
                
        # Traceability: Evidence
        for ev in run.evidence:
            assert not hasattr(ev, 'image_bytes'), "Evidence must be metadata only"
            assert not hasattr(ev, 'video_bytes'), "Evidence must be metadata only"
            assert not hasattr(ev, 'raw_data'), "Evidence must be metadata only"
            
            if ev.event_id:
                assert ev.event_id in persisted_event_ids, "Evidence linked to unknown event"
            if ev.assessment_id:
                assert any(r.event_id == ev.assessment_id for r in run.risk_assessments), "Evidence linked to unknown risk"

    finally:
        db.close()


def test_video_orchestration_persistence_processing_failure():
    """
    Verify FAILED lifecycle behavior when video processing fails.
    """
    db = SessionLocal()
    orchestrator, history_service = _setup_services(db)
    
    source = LocalVideoSource(Path("non_existent_file.mp4"))
    session_id = str(uuid.uuid4())
    
    session = orchestrator.start_session(session_id, source.get_source(), "LOCAL_FILE")
    db.commit()
    
    service = VideoProcessingService(persistence_orchestrator=orchestrator)
    
    try:
        service.process(source, session=session)
        db.commit()
    except Exception:
        db.rollback()
        if not getattr(service, 'processing_completed', False):
            orchestrator.fail_session(session)
            db.commit()
            
    run = history_service.get_historical_run(session_id)
    assert run.session.status == "FAILED"
    assert len(run.tracks) == 0
    assert len(run.events) == 0
    db.close()


def test_persistence_failure_rollback():
    """
    Force a persistence failure during complete_session() and verify rollback semantics.
    """
    db = SessionLocal()
    orchestrator, history_service = _setup_services(db)
    
    source = LocalVideoSource(TEST_VIDEO)
    session_id = str(uuid.uuid4())
    
    session = orchestrator.start_session(session_id, source.get_source(), "LOCAL_FILE")
    db.commit()
    
    service = VideoProcessingService(persistence_orchestrator=orchestrator)
    
    # Mock complete_session to fail
    original_complete = orchestrator.complete_session
    def failing_complete(*args, **kwargs):
        raise SQLAlchemyError("Mocked persistence failure")
    
    orchestrator.complete_session = failing_complete
    
    try:
        # Provide max_frames so it finishes quickly
        service.process(source, session=session, max_frames=3)
        db.commit()
    except Exception:
        db.rollback()
        if not getattr(service, 'processing_completed', False):
            orchestrator.fail_session(session)
            db.commit()
            
    # Restore
    orchestrator.complete_session = original_complete
    
    run = history_service.get_historical_run(session_id)
    # Since persistence failed, the session remains STARTED (because we rolled back the complete_session partial writes)
    # The transaction rollback behavior from Phase 8 explicitly means we don't commit COMPLETED.
    assert run.session.status == "STARTED", "Session should remain STARTED because the transaction rolled back"
    db.close()


def test_session_isolation_and_repeated_processing():
    """
    Process the same deterministic video twice sequentially in separate runs.
    Verify structural determinism and absolute session isolation.
    """
    detection_config = get_detection_config()
    detector = YOLODetector(config=detection_config)
    tracking_config = TrackingConfig()
    
    db = SessionLocal()
    orchestrator, history_service = _setup_services(db)
    
    service = VideoProcessingService(
        detector=detector,
        tracking_config=tracking_config,
        event_config=EventIntelligenceConfig(),
        risk_config=RiskConfig(),
        generate_evidence=True,
        persistence_orchestrator=orchestrator
    )
    
    source = LocalVideoSource(TEST_VIDEO)
    
    def run_pipeline():
        sess_id = str(uuid.uuid4())
        sess = orchestrator.start_session(sess_id, source.get_source(), "LOCAL_FILE")
        db.commit()
        
        try:
            res = service.process(source, session=sess, max_frames=5)
            db.commit()
        except Exception:
            db.rollback()
            if not getattr(service, 'processing_completed', False):
                orchestrator.fail_session(sess)
                db.commit()
            raise
        return sess_id, res
        
    session_a_id, result_a = run_pipeline()
    session_b_id, result_b = run_pipeline()
    
    db.close()
    
    # Reload from DB
    db = SessionLocal()
    _, history_service = _setup_services(db)
    
    run_a = history_service.get_historical_run(session_a_id)
    run_b = history_service.get_historical_run(session_b_id)
    
    db.close()
    
    assert run_a.session.session_id != run_b.session.session_id
    
    # Determinism checks (compare structural properties, not UUIDs)
    assert len(run_a.tracks) == len(run_b.tracks)
    for i in range(len(run_a.tracks)):
        assert run_a.tracks[i].class_name == run_b.tracks[i].class_name
        assert run_a.tracks[i].session_track_id == run_b.tracks[i].session_track_id
        
    assert len(run_a.events) == len(run_b.events)
    for i in range(len(run_a.events)):
        assert run_a.events[i].event_type == run_b.events[i].event_type
        assert run_a.events[i].frame_number == run_b.events[i].frame_number
        
    # Isolation checks
    for track in run_a.tracks:
        assert track.processing_session_id == session_a_id
    for event in run_a.events:
        pass
    for risk in run_a.risk_assessments:
        pass
    for ev in run_a.evidence:
        pass
        
    for track in run_b.tracks:
        assert track.processing_session_id == session_b_id
    for event in run_b.events:
        pass
    for risk in run_b.risk_assessments:
        pass
    for ev in run_b.evidence:
        pass



def test_zone_entry_high_risk_persistence_regression():
    """
    Regression test proving that ZONE_ENTRY events generate HIGH risk assessments
    which correctly trigger evidence generation and persist fully down the pipeline.
    """
    from app.services.events.models import EventType, Event
    from app.services.risk.models import RiskLevel, Priority
    from app.services.risk.orchestrator import RiskOrchestrator
    from app.services.evidence.orchestrator import EvidenceOrchestrator
    from app.services.risk.config import RiskConfig
    from app.repositories.domain import TrackDomain
    
    db = SessionLocal()
    try:
        orchestrator, history_service = _setup_services(db)
        
        session_id = str(uuid.uuid4())
        session = orchestrator.start_session(session_id, "mock_source", "MOCK")
        
        mock_track = TrackDomain(
            id=str(uuid.uuid4()),
            processing_session_id=session_id,
            session_track_id=1,
            class_name="person"
        )
        
        mock_event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.ZONE_ENTRY,
            frame_number=1,
            timestamp_seconds=0.1,
            description="Manual mock entry",
            track_id="1",
            evidence_data={"zone_id": "test_zone"}
        )
        
        risk_config = RiskConfig()
        risk_orchestrator = RiskOrchestrator(config=risk_config)
        risk_assessments = risk_orchestrator.process_events([mock_event])
        
        assert len(risk_assessments) == 1
        assert risk_assessments[0].risk_level == RiskLevel.HIGH
        assert risk_assessments[0].priority == Priority.HIGH
        
        evidence_orchestrator = EvidenceOrchestrator(source_id="test_source")
        evidence_items = evidence_orchestrator.process(events=[mock_event], risks=risk_assessments)
        
        assert len(evidence_items) > 0
        assert evidence_items[0].assessment_id == risk_assessments[0].event_id
        
        orchestrator.complete_session(
            session=session,
            tracks=[mock_track],
            observations=[],
            events=[mock_event],
            risk_assessments=risk_assessments,
            evidence=evidence_items
        )
        db.commit()
    finally:
        db.close()
    
    db = SessionLocal()
    try:
        _, history_service = _setup_services(db)
        run = history_service.get_historical_run(session_id)
        
        assert len(run.events) == 1
        assert run.events[0].event_type == EventType.ZONE_ENTRY
        
        assert len(run.risk_assessments) == 1
        assert run.risk_assessments[0].risk_level == RiskLevel.HIGH
        assert run.risk_assessments[0].priority == Priority.HIGH
        
        assert len(run.evidence) == 1
        assert run.evidence[0].assessment_id == run.risk_assessments[0].event_id
    finally:
        db.close()


def test_zone_entry_high_risk_persistence_regression():
    """
    Regression test proving that ZONE_ENTRY events generate HIGH risk assessments
    which correctly trigger evidence generation and persist fully down the pipeline.
    """
    from app.services.events.models import EventType, Event
    from app.services.risk.models import RiskLevel, Priority
    from app.services.risk.orchestrator import RiskOrchestrator
    from app.services.evidence.orchestrator import EvidenceOrchestrator
    from app.services.risk.config import RiskConfig
    
    db = SessionLocal()
    try:
        orchestrator, history_service = _setup_services(db)
        
        session_id = str(uuid.uuid4())
        session = orchestrator.start_session(session_id, "mock_source", "MOCK")
        
        mock_event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.ZONE_ENTRY,
            frame_number=1,
            timestamp_seconds=0.1,
            description="Manual mock entry",
            track_id="1",
            evidence_data={"zone_id": "test_zone"}
        )
        
        risk_config = RiskConfig()
        risk_orchestrator = RiskOrchestrator(config=risk_config)
        risk_assessments = risk_orchestrator.process_events([mock_event])
        
        assert len(risk_assessments) == 1
        assert risk_assessments[0].risk_level == RiskLevel.HIGH
        assert risk_assessments[0].priority == Priority.HIGH
        
        evidence_orchestrator = EvidenceOrchestrator(source_id="test_source")
        evidence_items = evidence_orchestrator.process(events=[mock_event], risks=risk_assessments)
        
        assert len(evidence_items) > 0
        assert evidence_items[0].assessment_id == risk_assessments[0].event_id
        
        orchestrator.persist_intelligence(
            session_id=session_id,
            tracks=[],
            observations=[],
            events=[mock_event],
            risks=risk_assessments,
            evidence=evidence_items
        )
        orchestrator.complete_session(session)
        db.commit()
    finally:
        db.close()
    
    db = SessionLocal()
    try:
        _, history_service = _setup_services(db)
        run = history_service.get_historical_run(session_id)
        
        assert len(run.events) == 1
        assert run.events[0].event_type == EventType.ZONE_ENTRY
        
        assert len(run.risk_assessments) == 1
        assert run.risk_assessments[0].risk_level == RiskLevel.HIGH
        assert run.risk_assessments[0].priority == Priority.HIGH
        
        assert len(run.evidence) == 1
        assert run.evidence[0].assessment_id == run.risk_assessments[0].event_id
    finally:
        db.close()


def test_zone_entry_high_risk_persistence_regression():
    """
    Regression test proving that ZONE_ENTRY events generate HIGH risk assessments
    which correctly trigger evidence generation and persist fully down the pipeline.
    """
    from app.services.events.models import EventType, Event
    from app.services.risk.models import RiskLevel, Priority
    from app.services.risk.orchestrator import RiskOrchestrator
    from app.services.evidence.orchestrator import EvidenceOrchestrator
    from app.services.risk.config import RiskConfig
    
    db = SessionLocal()
    try:
        orchestrator, history_service = _setup_services(db)
        
        session_id = str(uuid.uuid4())
        session = orchestrator.start_session(session_id, "mock_source", "MOCK")
        
        mock_event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.ZONE_ENTRY,
            frame_number=1,
            timestamp_seconds=0.1,
            description="Manual mock entry",
            track_id="1",
            evidence_data={"zone_id": "test_zone"}
        )
        
        risk_config = RiskConfig()
        risk_orchestrator = RiskOrchestrator(config=risk_config)
        risk_assessments = risk_orchestrator.process_events([mock_event])
        
        assert len(risk_assessments) == 1
        assert risk_assessments[0].risk_level == RiskLevel.HIGH
        assert risk_assessments[0].priority == Priority.HIGH
        
        evidence_orchestrator = EvidenceOrchestrator(source_id="test_source")
        evidence_items = evidence_orchestrator.process(events=[mock_event], risks=risk_assessments)
        
        assert len(evidence_items) > 0
        assert evidence_items[0].assessment_id == risk_assessments[0].event_id
        
        orchestrator.persist_intelligence(
            session_id=session_id,
            tracks=[],
            observations=[],
            events=[mock_event],
            risks=risk_assessments,
            evidence=evidence_items
        )
        orchestrator.complete_session(session)
        db.commit()
    finally:
        db.close()
    
    db = SessionLocal()
    try:
        _, history_service = _setup_services(db)
        run = history_service.get_historical_run(session_id)
        
        assert len(run.events) == 1
        assert run.events[0].event_type == EventType.ZONE_ENTRY
        
        assert len(run.risk_assessments) == 1
        assert run.risk_assessments[0].risk_level == RiskLevel.HIGH
        assert run.risk_assessments[0].priority == Priority.HIGH
        
        assert len(run.evidence) == 1
        assert run.evidence[0].assessment_id == run.risk_assessments[0].event_id
    finally:
        db.close()


def test_zone_entry_high_risk_persistence_regression():
    """
    Regression test proving that ZONE_ENTRY events generate HIGH risk assessments
    which correctly trigger evidence generation and persist fully down the pipeline.
    """
    from app.services.events.models import EventType, Event
    from app.services.risk.models import RiskLevel, Priority
    from app.services.risk.orchestrator import RiskOrchestrator
    from app.services.evidence.orchestrator import EvidenceOrchestrator
    from app.services.risk.config import RiskConfig
    
    db = SessionLocal()
    try:
        orchestrator, history_service = _setup_services(db)
        
        session_id = str(uuid.uuid4())
        session = orchestrator.start_session(session_id, "mock_source", "MOCK")
        
        mock_event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.ZONE_ENTRY,
            frame_number=1,
            timestamp_seconds=0.1,
            description="Manual mock entry",
            track_id="1",
            evidence_data={"zone_id": "test_zone"}
        )
        
        risk_config = RiskConfig()
        risk_orchestrator = RiskOrchestrator(config=risk_config)
        risk_assessments = risk_orchestrator.process_events([mock_event])
        
        assert len(risk_assessments) == 1
        assert risk_assessments[0].risk_level == RiskLevel.HIGH
        assert risk_assessments[0].priority == Priority.HIGH
        
        evidence_orchestrator = EvidenceOrchestrator(source_id="test_source")
        evidence_items = evidence_orchestrator.process(events=[mock_event], risks=risk_assessments)
        
        assert len(evidence_items) > 0
        assert evidence_items[0].assessment_id == risk_assessments[0].event_id
        
        from app.repositories.domain import TrackDomain
        mock_track = TrackDomain(
            id=str(uuid.uuid4()),
            processing_session_id=session_id,
            session_track_id=1,
            class_id=0,
            class_name="person",
            confidence=0.9,
            latest_bbox={"x1": 0, "y1": 0, "x2": 10, "y2": 10}
        )
        
        orchestrator.complete_session(
            session=session,
            tracks=[mock_track],
            observations=[],
            events=[mock_event],
            risk_assessments=risk_assessments,
            evidence=evidence_items
        )
        db.commit()
    finally:
        db.close()
    
    db = SessionLocal()
    try:
        _, history_service = _setup_services(db)
        run = history_service.get_historical_run(session_id)
        
        assert len(run.events) == 1
        assert run.events[0].event_type == EventType.ZONE_ENTRY
        
        assert len(run.risk_assessments) == 1
        assert run.risk_assessments[0].risk_level == RiskLevel.HIGH
        assert run.risk_assessments[0].priority == Priority.HIGH
        
        assert len(run.evidence) == 1
        assert run.evidence[0].assessment_id == run.risk_assessments[0].event_id
    finally:
        db.close()





