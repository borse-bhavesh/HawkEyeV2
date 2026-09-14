import pytest

from app.services.events.models import Event, EventType
from app.services.risk.models import RiskLevel, Priority, RiskAssessment
from app.services.risk.config import RiskConfig
from app.services.risk.policy import RiskPolicy, RiskPolicyRule
from app.services.risk.risk_engine import RiskEngine
from app.services.risk.risk_policy_engine import RiskPolicyEngine

@pytest.fixture
def engine():
    return RiskPolicyEngine(RiskConfig())

@pytest.fixture
def sample_event():
    return Event(
        event_id="evt-123",
        event_type=EventType.LOITERING,
        frame_number=10,
        timestamp_seconds=1.0,
        description="Test description",
        track_id=1,
        evidence={}
    )

def test_risk_policy_engine_implements_risk_engine(engine):
    assert isinstance(engine, RiskEngine)

def test_assess_accepts_existing_event(engine, sample_event):
    assessment = engine.assess(sample_event)
    assert assessment is not None

def test_assess_returns_risk_assessment(engine, sample_event):
    assessment = engine.assess(sample_event)
    assert isinstance(assessment, RiskAssessment)

def test_event_id_is_preserved(engine, sample_event):
    assessment = engine.assess(sample_event)
    assert assessment.event_id == "evt-123"

def test_contributing_event_id_is_preserved(engine, sample_event):
    assessment = engine.assess(sample_event)
    assert assessment.contributing_event_ids == ["evt-123"]

def test_contributing_event_type_is_preserved(engine, sample_event):
    assessment = engine.assess(sample_event)
    assert assessment.contributing_event_types == [EventType.LOITERING]

def test_configured_risk_level_is_returned(engine, sample_event):
    assessment = engine.assess(sample_event)
    assert assessment.risk_level == RiskLevel.HIGH

def test_configured_priority_is_returned(engine, sample_event):
    assessment = engine.assess(sample_event)
    assert assessment.priority == Priority.HIGH

def test_configured_reason_is_returned(engine, sample_event):
    assessment = engine.assess(sample_event)
    assert assessment.reason == "Configured policy classifies LOITERING for elevated review."

def test_different_event_types_use_their_rules(engine):
    evt1 = Event(event_id="e1", event_type=EventType.LOITERING, frame_number=1, timestamp_seconds=1.0, description="", track_id=1, evidence={})
    evt2 = Event(event_id="e2", event_type=EventType.TRACK_STARTED, frame_number=2, timestamp_seconds=2.0, description="", track_id=2, evidence={})
    
    ass1 = engine.assess(evt1)
    ass2 = engine.assess(evt2)
    
    assert ass1.risk_level == RiskLevel.HIGH
    assert ass2.risk_level == RiskLevel.LOW

def test_custom_policy_overrides_default_behavior():
    rules = RiskPolicy.default().rules
    rules[EventType.LOITERING] = RiskPolicyRule(
        risk_level=RiskLevel.LOW,
        priority=Priority.LOW,
        reason_template="Custom"
    )
    custom_engine = RiskPolicyEngine(RiskConfig(), RiskPolicy(rules=rules))
    
    evt = Event(event_id="e1", event_type=EventType.LOITERING, frame_number=1, timestamp_seconds=1.0, description="", track_id=1, evidence={})
    assessment = custom_engine.assess(evt)
    
    assert assessment.risk_level == RiskLevel.LOW
    assert assessment.reason == "Custom"

def test_unknown_event_type_fails_clearly(engine):
    # Mocking an unknown event type string, bypassing validation
    evt = Event.model_construct(event_id="e1", event_type="UNKNOWN_TYPE_FOR_TEST", frame_number=1, timestamp_seconds=1.0, description="", track_id=1, evidence={})
    with pytest.raises(KeyError):
        engine.assess(evt)

def test_input_event_is_not_mutated(engine, sample_event):
    original_dict = sample_event.model_dump()
    engine.assess(sample_event)
    assert sample_event.model_dump() == original_dict

def test_assess_events_empty_returns_empty(engine):
    assert engine.assess_events([]) == []

def test_assess_events_returns_one_assessment_per_input_event(engine):
    evt1 = Event(event_id="e1", event_type=EventType.LOITERING, frame_number=1, timestamp_seconds=1.0, description="", track_id=1, evidence={})
    evt2 = Event(event_id="e2", event_type=EventType.TRACK_STARTED, frame_number=2, timestamp_seconds=2.0, description="", track_id=2, evidence={})
    
    assessments = engine.assess_events([evt1, evt2])
    assert len(assessments) == 2

def test_batch_order_matches_input_order(engine):
    evt1 = Event(event_id="e1", event_type=EventType.LOITERING, frame_number=1, timestamp_seconds=1.0, description="", track_id=1, evidence={})
    evt2 = Event(event_id="e2", event_type=EventType.TRACK_STARTED, frame_number=2, timestamp_seconds=2.0, description="", track_id=2, evidence={})
    
    assessments = engine.assess_events([evt1, evt2])
    assert assessments[0].event_id == "e1"
    assert assessments[1].event_id == "e2"

def test_batch_assessments_preserve_individual_event_ids(engine):
    evt1 = Event(event_id="e1", event_type=EventType.LOITERING, frame_number=1, timestamp_seconds=1.0, description="", track_id=1, evidence={})
    evt2 = Event(event_id="e2", event_type=EventType.TRACK_STARTED, frame_number=2, timestamp_seconds=2.0, description="", track_id=2, evidence={})
    
    assessments = engine.assess_events([evt1, evt2])
    assert assessments[0].contributing_event_ids == ["e1"]
    assert assessments[1].contributing_event_ids == ["e2"]

def test_same_event_same_policy_produces_deterministic_result(engine, sample_event):
    ass1 = engine.assess(sample_event)
    ass2 = engine.assess(sample_event)
    assert ass1.model_dump() == ass2.model_dump()

def test_engine_has_no_cross_event_state(engine):
    # Test that evaluating event 1 doesn't change outcome of event 2
    evt1 = Event(event_id="e1", event_type=EventType.LOITERING, frame_number=1, timestamp_seconds=1.0, description="", track_id=1, evidence={})
    evt2 = Event(event_id="e2", event_type=EventType.TRACK_STARTED, frame_number=2, timestamp_seconds=2.0, description="", track_id=2, evidence={})
    
    ass_evt2_before = engine.assess(evt2)
    engine.assess(evt1)
    ass_evt2_after = engine.assess(evt2)
    
    assert ass_evt2_before.model_dump() == ass_evt2_after.model_dump()

def test_engine_does_not_produce_numeric_risk_scores(engine, sample_event):
    assessment = engine.assess(sample_event)
    assert not hasattr(assessment, "score")
    assert not hasattr(assessment, "weight")

def test_no_risk_assessment_claims_intent_or_criminality(engine, sample_event):
    assessment = engine.assess(sample_event)
    reason = assessment.reason.lower()
    assert "criminal" not in reason
    assert "intent" not in reason
    assert "suspicious" not in reason
    assert "dangerous" not in reason
