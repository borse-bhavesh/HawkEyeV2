import os
import uuid
import sys
sys.path.append(r'D:\HawkEye_V2\backend')

from app.db.database import SessionLocal as RealSessionLocal
from app.db.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.api.routes.sessions import get_core_service, get_evidence_service, get_history_service
from app.services.persistence.orchestrator import ProcessingPersistenceOrchestrator
from app.services.events.models import EventType, Event
from app.services.risk.models import RiskLevel, Priority
from app.services.risk.orchestrator import RiskOrchestrator
from app.services.evidence.orchestrator import EvidenceOrchestrator
from app.services.risk.config import RiskConfig

TEST_DB_URL = "postgresql+psycopg://hawkeye:hawkeye@localhost:5432/hawkeye_test"
test_engine = create_engine(TEST_DB_URL)
SessionLocal = sessionmaker(bind=test_engine)

def _setup_services(db):
    core_service = get_core_service(db)
    evidence_service = get_evidence_service(db)
    orchestrator = ProcessingPersistenceOrchestrator(core_service, evidence_service)
    history_service = get_history_service(core_service, evidence_service)
    return orchestrator, history_service

def run_test():
    print("Setting up DB...")
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
    
    print("Services setup...")
    db = SessionLocal()
    orchestrator, history_service = _setup_services(db)
    
    session_id = str(uuid.uuid4())
    print("Starting session...")
    session = orchestrator.start_session(session_id, "mock_source", "MOCK")
    
    print("Creating event...")
    mock_event = Event(
        event_id=str(uuid.uuid4()),
        event_type=EventType.ZONE_ENTRY,
        frame_number=1,
        timestamp_seconds=0.1,
        description="Manual mock entry",
        track_id="1",
        evidence_data={"zone_id": "test_zone"}
    )
    
    print("Risk orchestrator...")
    risk_config = RiskConfig()
    risk_orchestrator = RiskOrchestrator(config=risk_config)
    risk_assessments = risk_orchestrator.process_events([mock_event])
    
    assert len(risk_assessments) == 1
    assert risk_assessments[0].risk_level == RiskLevel.HIGH
    assert risk_assessments[0].priority == Priority.HIGH
    
    print("Evidence orchestrator...")
    evidence_orchestrator = EvidenceOrchestrator(source_id="test_source")
    evidence_items = evidence_orchestrator.process(events=[mock_event], risks=risk_assessments)
    
    assert len(evidence_items) > 0
    assert evidence_items[0].assessment_id == risk_assessments[0].id
    
    print("Persisting...")
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
    db.close()
    
    print("Verifying...")
    db = SessionLocal()
    _, history_service = _setup_services(db)
    run = history_service.get_historical_run(session_id)
    db.close()
    
    assert len(run.events) == 1
    assert run.events[0].event_type == EventType.ZONE_ENTRY
    
    assert len(run.risk_assessments) == 1
    assert run.risk_assessments[0].risk_level == RiskLevel.HIGH
    assert run.risk_assessments[0].priority == Priority.HIGH
    
    assert len(run.evidence) == 1
    assert run.evidence[0].assessment_id == run.risk_assessments[0].id
    
    print("Test passed!")

if __name__ == "__main__":
    run_test()
