from copy import deepcopy
from typing import List

from app.services.events.models import Event, EventType
from app.services.risk.config import RiskConfig
from app.services.risk.models import RiskLevel, Priority, RiskAssessment
from app.services.risk.orchestrator import RiskOrchestrator

def create_event(id_str: str, type_val: EventType, ts: float, track: int) -> Event:
    return Event(
        event_id=id_str,
        event_type=type_val,
        frame_number=int(ts * 30),
        timestamp_seconds=ts,
        description="Test",
        track_id=track,
        evidence={}
    )

def test_risk_orchestrator_policy_integration():
    """A. Policy integration: Known event produces assessment through real RiskPolicyEngine."""
    config = RiskConfig()
    orchestrator = RiskOrchestrator(config=config)
    
    evt = create_event("e1", EventType.ZONE_ENTRY, 1.0, track=1)
    
    assessments = orchestrator.process_events([evt])
    assert len(assessments) == 1
    assert assessments[0].risk_level == RiskLevel.HIGH
    assert assessments[0].priority == Priority.HIGH
    assert EventType.ZONE_ENTRY in assessments[0].contributing_event_types

def test_risk_orchestrator_correlation_integration():
    """B. Correlation integration: Correlated events trigger correlation assessment."""
    config = RiskConfig()
    orchestrator = RiskOrchestrator(config=config)
    
    # ZONE_ENTRY + LOITERING matches the default correlation policy for HIGH/HIGH
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, track=1)
    evt2 = create_event("e2", EventType.LOITERING, 2.0, track=1)
    
    assessments = orchestrator.process_events([evt1, evt2])
    
    # Policy creates 1 for ZONE_ENTRY and 1 for LOITERING
    # Correlation creates 1 for ZONE_ENTRY+LOITERING
    # So we expect 3 assessments total
    assert len(assessments) == 3
    
    # Find the correlated one
    correlated = [a for a in assessments if len(a.contributing_event_ids) > 1]
    assert len(correlated) == 1
    assert correlated[0].risk_level == RiskLevel.HIGH
    assert correlated[0].priority == Priority.HIGH

def test_risk_orchestrator_escalation_integration():
    """C. Escalation integration: Trigger escalation according to existing rules."""
    config = RiskConfig()
    orchestrator = RiskOrchestrator(config=config)
    
    # Multiple LOITERING events trigger the default escalation policy 
    # to elevate to CRITICAL/CRITICAL
    evt1 = create_event("e1", EventType.LOITERING, 1.0, track=1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, track=1)
    
    assessments = orchestrator.process_events([evt1, evt2])
    
    # Policy creates 2 for LOITERING (HIGH/HIGH)
    # Escalation engine should escalate them because there are multiple loitering events
    # So they should be converted to CRITICAL
    critical_assessments = [a for a in assessments if a.risk_level == RiskLevel.CRITICAL]
    assert len(critical_assessments) > 0

def test_risk_orchestrator_deduplication():
    """D. Deduplication: Duplicate equivalent events trigger deduplication."""
    config = RiskConfig()
    orchestrator = RiskOrchestrator(config=config)
    
    # Two identical events (e.g. from overlapping tracks or exact same time)
    # Actually deduplication is by identity hash of assessment
    # If policy engine creates identical assessments for same events (which it shouldn't normally if IDs differ)
    # Let's pass the EXACT same event twice (which shouldn't happen, but tests deduplication engine behavior)
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, track=1)
    evt2 = create_event("e1", EventType.ZONE_ENTRY, 1.0, track=1)
    
    assessments = orchestrator.process_events([evt1, evt2])
    # The policy engine creates 2 assessments.
    # Deduplication should reduce them to 1 because they are identical
    assert len(assessments) == 1

def test_risk_orchestrator_ordering():
    """E. Ordering: Deterministic assessment ordering for a deterministic event sequence."""
    config = RiskConfig()
    orchestrator = RiskOrchestrator(config=config)
    
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, track=1)
    evt2 = create_event("e2", EventType.LOITERING, 2.0, track=1)
    evt3 = create_event("e3", EventType.RAPID_MOVEMENT, 3.0, track=1)
    
    assessments_1 = orchestrator.process_events([evt1, evt2, evt3])
    
    orchestrator2 = RiskOrchestrator(config=config)
    assessments_2 = orchestrator2.process_events([evt1, evt2, evt3])
    
    assert len(assessments_1) == len(assessments_2)
    for i in range(len(assessments_1)):
        assert assessments_1[i].event_id == assessments_2[i].event_id

def test_risk_orchestrator_input_immutability():
    """F. Input immutability: Event inputs not mutated."""
    config = RiskConfig()
    orchestrator = RiskOrchestrator(config=config)
    
    evt = create_event("e1", EventType.ZONE_ENTRY, 1.0, track=1)
    original_dict = deepcopy(evt.model_dump())
    
    orchestrator.process_events([evt])
    assert evt.model_dump() == original_dict

def test_risk_orchestrator_run_isolation():
    """G. Run isolation: Two RiskOrchestrator instances don't share state."""
    config = RiskConfig()
    orch1 = RiskOrchestrator(config=config)
    orch2 = RiskOrchestrator(config=config)
    
    assert orch1.policy_engine is not orch2.policy_engine
    assert orch1.correlation_engine is not orch2.correlation_engine
    assert orch1.escalation_engine is not orch2.escalation_engine

def test_risk_orchestrator_empty_input():
    """H. Empty input: empty event list."""
    config = RiskConfig()
    orchestrator = RiskOrchestrator(config=config)
    assert orchestrator.process_events([]) == []

def test_risk_orchestrator_disabled_config():
    """I. Disabled config: enabled=False."""
    config = RiskConfig(enabled=False)
    orchestrator = RiskOrchestrator(config=config)
    evt = create_event("e1", EventType.ZONE_ENTRY, 1.0, track=1)
    assert orchestrator.process_events([evt]) == []
