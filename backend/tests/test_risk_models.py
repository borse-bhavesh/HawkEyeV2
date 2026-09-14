import pytest
from pydantic import ValidationError

from app.services.events.models import Event, EventType
from app.services.risk.models import RiskLevel, Priority, RiskAssessment, RiskAssessmentStatus
from app.services.risk.config import RiskConfig
from app.services.risk.risk_policy_engine import RiskPolicyEngine
from app.services.risk.correlation_engine import RiskCorrelationEngine

def test_risk_level_enum_values():
    assert RiskLevel.LOW == "low"
    assert RiskLevel.MEDIUM == "medium"
    assert RiskLevel.HIGH == "high"
    assert RiskLevel.CRITICAL == "critical"

def test_priority_enum_values():
    assert Priority.LOW == "low"
    assert Priority.MEDIUM == "medium"
    assert Priority.HIGH == "high"
    assert Priority.CRITICAL == "critical"

def test_valid_risk_assessment_construction():
    assessment = RiskAssessment(
        event_id="evt-123",
        risk_level=RiskLevel.MEDIUM,
        priority=Priority.HIGH,
        reason="Assessment based on configured policy."
    )
    assert assessment.event_id == "evt-123"
    assert assessment.risk_level == RiskLevel.MEDIUM
    assert assessment.priority == Priority.HIGH
    assert assessment.reason == "Assessment based on configured policy."
    assert assessment.contributing_event_ids == []
    assert assessment.contributing_event_types == []

def test_invalid_risk_level_rejected():
    with pytest.raises(ValidationError):
        RiskAssessment(
            event_id="evt-123",
            risk_level="INVALID",
            priority=Priority.HIGH,
            reason="Test"
        )

def test_invalid_priority_rejected():
    with pytest.raises(ValidationError):
        RiskAssessment(
            event_id="evt-123",
            risk_level=RiskLevel.MEDIUM,
            priority="INVALID",
            reason="Test"
        )

def test_empty_reason_rejected():
    with pytest.raises(ValidationError):
        RiskAssessment(
            event_id="evt-123",
            risk_level=RiskLevel.MEDIUM,
            priority=Priority.HIGH,
            reason=""
        )

def test_empty_event_id_rejected():
    with pytest.raises(ValidationError):
        RiskAssessment(
            event_id="",
            risk_level=RiskLevel.MEDIUM,
            priority=Priority.HIGH,
            reason="Test"
        )

def test_event_traceability_fields_preserved():
    assessment = RiskAssessment(
        event_id="evt-123",
        contributing_event_ids=["evt-123", "evt-456"],
        risk_level=RiskLevel.MEDIUM,
        priority=Priority.HIGH,
        reason="Test"
    )
    assert assessment.contributing_event_ids == ["evt-123", "evt-456"]

def test_multiple_contributing_event_ids_supported():
    assessment = RiskAssessment(
        event_id="composite-1",
        contributing_event_ids=["evt-1", "evt-2", "evt-3"],
        risk_level=RiskLevel.HIGH,
        priority=Priority.HIGH,
        reason="Test"
    )
    assert len(assessment.contributing_event_ids) == 3

def test_existing_event_type_values_can_be_used():
    assessment = RiskAssessment(
        event_id="evt-1",
        contributing_event_types=[EventType.LOITERING, EventType.RAPID_MOVEMENT],
        risk_level=RiskLevel.CRITICAL,
        priority=Priority.CRITICAL,
        reason="Test"
    )
    assert EventType.LOITERING in assessment.contributing_event_types
    assert EventType.RAPID_MOVEMENT in assessment.contributing_event_types

def test_model_serialization_is_deterministic():
    assessment = RiskAssessment(
        event_id="evt-123",
        risk_level=RiskLevel.MEDIUM,
        priority=Priority.HIGH,
        reason="Test"
    )
    data = assessment.model_dump()
    assert data["risk_level"] == "medium"
    assert data["priority"] == "high"

# --- New Lifecycle Tests for Step 6.4A ---

def test_risk_assessment_status_enum_values():
    assert RiskAssessmentStatus.OPEN == "open"
    assert RiskAssessmentStatus.ACKNOWLEDGED == "acknowledged"
    assert RiskAssessmentStatus.RESOLVED == "resolved"
    assert len(RiskAssessmentStatus) == 3

def test_new_risk_assessment_defaults_to_open():
    assessment = RiskAssessment(
        event_id="evt-123",
        risk_level=RiskLevel.LOW,
        priority=Priority.LOW,
        reason="Test"
    )
    assert assessment.status == RiskAssessmentStatus.OPEN

def test_existing_fields_remain_valid():
    assessment = RiskAssessment(
        event_id="evt-123",
        contributing_event_ids=["evt-1"],
        contributing_event_types=[EventType.ZONE_ENTRY],
        risk_level=RiskLevel.LOW,
        priority=Priority.LOW,
        reason="Test"
    )
    assert assessment.event_id == "evt-123"
    assert assessment.contributing_event_ids == ["evt-1"]
    assert assessment.contributing_event_types == [EventType.ZONE_ENTRY]
    assert assessment.risk_level == RiskLevel.LOW
    assert assessment.priority == Priority.LOW
    assert assessment.reason == "Test"

def test_open_to_acknowledged_succeeds():
    assessment = RiskAssessment(event_id="1", risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="Test")
    assessment.transition_to(RiskAssessmentStatus.ACKNOWLEDGED)
    assert assessment.status == RiskAssessmentStatus.ACKNOWLEDGED

def test_acknowledged_to_resolved_succeeds():
    assessment = RiskAssessment(event_id="1", risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="Test")
    assessment.transition_to(RiskAssessmentStatus.ACKNOWLEDGED)
    assessment.transition_to(RiskAssessmentStatus.RESOLVED)
    assert assessment.status == RiskAssessmentStatus.RESOLVED

def test_open_to_open_is_idempotent():
    assessment = RiskAssessment(event_id="1", risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="Test")
    assessment.transition_to(RiskAssessmentStatus.OPEN)
    assert assessment.status == RiskAssessmentStatus.OPEN

def test_acknowledged_to_acknowledged_is_idempotent():
    assessment = RiskAssessment(event_id="1", risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="Test")
    assessment.transition_to(RiskAssessmentStatus.ACKNOWLEDGED)
    assessment.transition_to(RiskAssessmentStatus.ACKNOWLEDGED)
    assert assessment.status == RiskAssessmentStatus.ACKNOWLEDGED

def test_resolved_to_resolved_is_idempotent():
    assessment = RiskAssessment(event_id="1", risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="Test")
    assessment.transition_to(RiskAssessmentStatus.ACKNOWLEDGED)
    assessment.transition_to(RiskAssessmentStatus.RESOLVED)
    assessment.transition_to(RiskAssessmentStatus.RESOLVED)
    assert assessment.status == RiskAssessmentStatus.RESOLVED

def test_acknowledged_to_open_raises_value_error():
    assessment = RiskAssessment(event_id="1", risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="Test")
    assessment.transition_to(RiskAssessmentStatus.ACKNOWLEDGED)
    with pytest.raises(ValueError, match="Invalid lifecycle transition"):
        assessment.transition_to(RiskAssessmentStatus.OPEN)

def test_resolved_to_acknowledged_raises_value_error():
    assessment = RiskAssessment(event_id="1", risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="Test")
    assessment.transition_to(RiskAssessmentStatus.ACKNOWLEDGED)
    assessment.transition_to(RiskAssessmentStatus.RESOLVED)
    with pytest.raises(ValueError, match="Invalid lifecycle transition"):
        assessment.transition_to(RiskAssessmentStatus.ACKNOWLEDGED)

def test_resolved_to_open_raises_value_error():
    assessment = RiskAssessment(event_id="1", risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="Test")
    assessment.transition_to(RiskAssessmentStatus.ACKNOWLEDGED)
    assessment.transition_to(RiskAssessmentStatus.RESOLVED)
    with pytest.raises(ValueError, match="Invalid lifecycle transition"):
        assessment.transition_to(RiskAssessmentStatus.OPEN)

def test_transition_to_does_not_modify_risk_level():
    assessment = RiskAssessment(event_id="1", risk_level=RiskLevel.MEDIUM, priority=Priority.LOW, reason="Test")
    assessment.transition_to(RiskAssessmentStatus.ACKNOWLEDGED)
    assert assessment.risk_level == RiskLevel.MEDIUM

def test_transition_to_does_not_modify_priority():
    assessment = RiskAssessment(event_id="1", risk_level=RiskLevel.LOW, priority=Priority.HIGH, reason="Test")
    assessment.transition_to(RiskAssessmentStatus.ACKNOWLEDGED)
    assert assessment.priority == Priority.HIGH

def test_transition_to_does_not_modify_reason():
    assessment = RiskAssessment(event_id="1", risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="Test")
    assessment.transition_to(RiskAssessmentStatus.ACKNOWLEDGED)
    assert assessment.reason == "Test"

def test_transition_to_does_not_modify_event_id():
    assessment = RiskAssessment(event_id="evt-123", risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="Test")
    assessment.transition_to(RiskAssessmentStatus.ACKNOWLEDGED)
    assert assessment.event_id == "evt-123"

def test_transition_to_does_not_modify_contributing_event_ids():
    assessment = RiskAssessment(event_id="1", contributing_event_ids=["c1", "c2"], risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="Test")
    assessment.transition_to(RiskAssessmentStatus.ACKNOWLEDGED)
    assert assessment.contributing_event_ids == ["c1", "c2"]

def test_transition_to_does_not_modify_contributing_event_types():
    assessment = RiskAssessment(
        event_id="1", 
        contributing_event_types=[EventType.ZONE_ENTRY], 
        risk_level=RiskLevel.LOW, 
        priority=Priority.LOW, 
        reason="Test"
    )
    assessment.transition_to(RiskAssessmentStatus.ACKNOWLEDGED)
    assert assessment.contributing_event_types == [EventType.ZONE_ENTRY]

def test_risk_policy_engine_created_assessments_start_open():
    engine = RiskPolicyEngine(RiskConfig())
    evt = Event(event_id="e1", event_type=EventType.LOITERING, frame_number=1, timestamp_seconds=1.0, description="", track_id=1, evidence={})
    assessment = engine.assess(evt)
    assert assessment.status == RiskAssessmentStatus.OPEN

def test_risk_correlation_engine_created_assessments_start_open():
    engine = RiskCorrelationEngine()
    evt1 = Event(event_id="e1", event_type=EventType.ZONE_ENTRY, frame_number=1, timestamp_seconds=1.0, description="", track_id=1, evidence={})
    evt2 = Event(event_id="e2", event_type=EventType.LOITERING, frame_number=2, timestamp_seconds=2.0, description="", track_id=1, evidence={})
    assessments = engine.correlate([evt1, evt2])
    assert len(assessments) == 1
    assert assessments[0].status == RiskAssessmentStatus.OPEN

def test_repeated_valid_transition_calls_are_deterministic():
    assessment = RiskAssessment(event_id="1", risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="Test")
    assessment.transition_to(RiskAssessmentStatus.ACKNOWLEDGED)
    assessment.transition_to(RiskAssessmentStatus.ACKNOWLEDGED)
    assessment.transition_to(RiskAssessmentStatus.RESOLVED)
    assessment.transition_to(RiskAssessmentStatus.RESOLVED)
    assert assessment.status == RiskAssessmentStatus.RESOLVED
