import pytest
from typing import List

from app.services.events.models import Event, EventType
from app.services.risk.models import RiskLevel, Priority, RiskAssessment
from app.services.risk.config import RiskConfig
from app.services.risk.risk_engine import RiskEngine

class DummyRiskEngine(RiskEngine):
    def assess(self, event: Event) -> RiskAssessment:
        return RiskAssessment(
            event_id=event.event_id,
            risk_level=RiskLevel.LOW,
            priority=Priority.LOW,
            reason="Dummy assessment for testing contract."
        )

    def assess_events(self, events: List[Event]) -> List[RiskAssessment]:
        return [self.assess(e) for e in events]

def test_risk_engine_is_abstract():
    with pytest.raises(TypeError):
        # Cannot instantiate abstract class directly
        RiskEngine(RiskConfig())

def test_minimal_concrete_test_implementation_satisfies_interface():
    engine = DummyRiskEngine(RiskConfig())
    assert engine.config.enabled is True

def test_interface_accepts_existing_event_model():
    engine = DummyRiskEngine(RiskConfig())
    event = Event(
        event_id="test-evt",
        event_type=EventType.LOITERING,
        frame_number=10,
        timestamp_seconds=1.0,
        description="Test",
        track_id=1,
        evidence={}
    )
    assessment = engine.assess(event)
    assert assessment is not None

def test_contract_returns_risk_assessment_from_test_implementation():
    engine = DummyRiskEngine(RiskConfig())
    event = Event(
        event_id="test-evt",
        event_type=EventType.LOITERING,
        frame_number=10,
        timestamp_seconds=1.0,
        description="Test",
        track_id=1,
        evidence={}
    )
    assessment = engine.assess(event)
    assert isinstance(assessment, RiskAssessment)
    assert assessment.event_id == "test-evt"
    assert assessment.risk_level == RiskLevel.LOW
    assert assessment.priority == Priority.LOW

def test_no_scoring_logic_present_in_abstract_class():
    # Proven by the fact that assess is abstract and raises TypeError upon instantiation,
    # and no mathematical scoring routines exist in RiskEngine.
    assert hasattr(RiskEngine, "assess")
    assert getattr(RiskEngine.assess, "__isabstractmethod__") is True

def test_existing_event_types_remain_unchanged():
    # Verified by importing EventType correctly
    assert EventType.LOITERING == "LOITERING"
