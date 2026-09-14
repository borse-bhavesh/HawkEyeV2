from copy import deepcopy

from app.services.events.models import Event, EventType
from app.services.risk.models import RiskAssessment, RiskLevel, Priority, RiskAssessmentStatus, RiskAssessmentEvidence, EvidenceSourceType
from app.services.evidence.models import EvidenceType
from app.services.evidence.orchestrator import EvidenceOrchestrator
from app.services.evidence.linker import EvidenceLinkingService

def create_event(event_id: str, frame: int, ts: float) -> Event:
    return Event(
        event_id=event_id,
        event_type=EventType.ZONE_ENTRY,
        frame_number=frame,
        timestamp_seconds=ts,
        description="test",
        track_id=1,
        evidence={}
    )

def create_risk(assessment_id: str, contributing_event_ids: list[str]) -> RiskAssessment:
    # Phase 6 uses event_id as the assessment_id
    return RiskAssessment(
        event_id=assessment_id,
        contributing_event_ids=contributing_event_ids,
        contributing_event_types=[EventType.ZONE_ENTRY],
        risk_level=RiskLevel.MEDIUM,
        priority=Priority.MEDIUM,
        reason="Test",
        status=RiskAssessmentStatus.OPEN,
        evidence=RiskAssessmentEvidence(
            source_type=EvidenceSourceType.POLICY,
            policy_identifier="rule_1",
            explanation="Test explanation"
        )
    )

def test_event_to_frame_evidence():
    """A. Event -> Frame Evidence: Given a valid event, verify appropriate metadata-only evidence is produced."""
    orchestrator = EvidenceOrchestrator(source_id="cam_test")
    evt = create_event("e1", 100, 3.3)
    
    evidence_list = orchestrator.process([evt], [])
    
    assert len(evidence_list) == 1
    ev = evidence_list[0]
    assert ev.evidence_type == EvidenceType.FRAME
    assert ev.event_id == "e1"
    assert ev.assessment_id is None

def test_risk_evidence_linking():
    """B. Risk -> Evidence Linking: Given a valid RiskAssessment, verify evidence can be linked."""
    orchestrator = EvidenceOrchestrator(source_id="cam_test")
    evt = create_event("e1", 100, 3.3)
    risk = create_risk("risk_1", ["e1"])
    
    evidence_list = orchestrator.process([evt], [risk])
    
    # We should have exactly 1 evidence object that is linked to BOTH the event and the risk
    assert len(evidence_list) == 1
    ev = evidence_list[0]
    assert ev.evidence_type == EvidenceType.FRAME
    assert ev.event_id == "e1"
    assert ev.assessment_id == "risk_1"

def test_multiple_risks_for_same_event_clones_evidence():
    """B. Risk -> Evidence Linking (cloning): If multiple risks use the same event, it clones the evidence."""
    orchestrator = EvidenceOrchestrator(source_id="cam_test")
    evt = create_event("e1", 100, 3.3)
    risk1 = create_risk("risk_1", ["e1"])
    risk2 = create_risk("risk_2", ["e1"])
    
    evidence_list = orchestrator.process([evt], [risk1, risk2])
    
    # One for risk1 (which updated the base event evidence), one cloned for risk2
    assert len(evidence_list) == 2
    assert evidence_list[0].assessment_id == "risk_1"
    assert evidence_list[1].assessment_id == "risk_2"
    assert evidence_list[0].evidence_id != evidence_list[1].evidence_id

def test_metadata_only_guarantee():
    """C. Metadata-only guarantee: Verify generated Evidence contains no raw media bytes."""
    orchestrator = EvidenceOrchestrator(source_id="cam_test")
    evt = create_event("e1", 100, 3.3)
    
    evidence_list = orchestrator.process([evt], [])
    ev = evidence_list[0]
    
    # Assert it contains no raw bytes
    assert not hasattr(ev, 'image_bytes')
    assert not hasattr(ev, 'raw_data')
    assert not hasattr(ev, 'video_bytes')
    assert ev.frame is not None
    # the frame evidence shouldn't have any raw data
    assert not hasattr(ev.frame, 'image_bytes')

def test_exact_source_metadata():
    """D. Exact source metadata: Verify frame number and timestamp are copied from event."""
    orchestrator = EvidenceOrchestrator(source_id="cam_test")
    evt = create_event("e1", 42, 1.4)
    
    evidence_list = orchestrator.process([evt], [])
    ev = evidence_list[0]
    
    assert ev.source.source_id == "cam_test"
    assert ev.frame.frame_number == 42
    assert ev.frame.timestamp_seconds == 1.4

def test_deterministic_ordering():
    """F. Deterministic ordering: The same inputs must produce the same Evidence ordering."""
    evt1 = create_event("e1", 10, 0.3)
    evt2 = create_event("e2", 20, 0.6)
    risk = create_risk("risk_1", ["e1"])
    
    orch1 = EvidenceOrchestrator(source_id="cam_test")
    orch2 = EvidenceOrchestrator(source_id="cam_test")
    
    res1 = orch1.process([evt1, evt2], [risk])
    res2 = orch2.process([evt1, evt2], [risk])
    
    assert len(res1) == len(res2) == 2
    # The order of event_ids should be exactly e1 then e2, and assessment_ids should match
    assert res1[0].event_id == res2[0].event_id == "e1"
    assert res1[0].assessment_id == res2[0].assessment_id == "risk_1"
    assert res1[1].event_id == res2[1].event_id == "e2"
    assert res1[1].assessment_id is None
    assert res2[1].assessment_id is None

def test_input_immutability():
    """G. Input immutability: Verify Event and RiskAssessment inputs are not mutated."""
    orchestrator = EvidenceOrchestrator(source_id="cam_test")
    evt = create_event("e1", 42, 1.4)
    risk = create_risk("risk_1", ["e1"])
    
    evt_dump = deepcopy(evt.model_dump())
    risk_dump = deepcopy(risk.model_dump())
    
    orchestrator.process([evt], [risk])
    
    assert evt.model_dump() == evt_dump
    assert risk.model_dump() == risk_dump

def test_empty_input():
    """H. Empty input: Empty events/risks safely produce empty evidence list."""
    orchestrator = EvidenceOrchestrator(source_id="cam_test")
    assert orchestrator.process([], []) == []

def test_run_isolation():
    """I. Run isolation: Two instances must not share mutable state."""
    orch1 = EvidenceOrchestrator(source_id="cam_test")
    orch2 = EvidenceOrchestrator(source_id="cam_test")
    assert orch1.linker is not orch2.linker

def test_existing_phase_7_validation():
    """J. Existing Phase 7 validation: Uses real Phase 7 models."""
    orchestrator = EvidenceOrchestrator(source_id="cam_test")
    # This orchestrator uses the real EvidenceLinkingService
    assert isinstance(orchestrator.linker, EvidenceLinkingService)
