import pytest
import uuid
from pydantic import ValidationError

from app.services.events.models import Event, EventType
from app.services.risk.models import RiskAssessment, RiskLevel, Priority, RiskAssessmentStatus, RiskAssessmentEvidence, EvidenceSourceType
from app.services.risk.policy import RiskPolicy, RiskPolicyRule
from app.services.risk.risk_policy_engine import RiskPolicyEngine
from app.services.risk.correlation import RiskCorrelationPolicy, RiskCorrelationRule
from app.services.risk.correlation_engine import RiskCorrelationEngine
from app.services.risk.escalation import RiskEscalationPolicy, RiskDeescalationPolicy, RiskEscalationRule, RiskDeescalationRule
from app.services.risk.escalation_engine import RiskEscalationEngine
from app.services.risk.deduplication import RiskDeduplicationPolicy
from app.services.risk.deduplication_engine import RiskDeduplicationEngine

def create_event(event_type: EventType, event_id: str, track_id: int = 1, timestamp: float = 1.0):
    return Event(
        event_id=event_id,
        event_type=event_type,
        frame_number=int(timestamp * 30),
        timestamp_seconds=timestamp,
        description="test",
        track_id=track_id
    )

def test_valid_evidence_construction():
    evidence = RiskAssessmentEvidence(
        source_type=EvidenceSourceType.POLICY,
        policy_identifier="rule_123",
        contributing_event_ids=["e1"],
        contributing_event_types=[EventType.LOITERING],
        explanation="Test explanation",
        details={"key": "value"}
    )
    assert evidence.source_type == EvidenceSourceType.POLICY

def test_invalid_source_type_rejected():
    with pytest.raises(ValidationError):
        RiskAssessmentEvidence(
            source_type="INVALID_TYPE",
            policy_identifier="rule_123",
            explanation="Test explanation"
        )

def test_empty_policy_identifier_rejected():
    with pytest.raises(ValidationError):
        RiskAssessmentEvidence(
            source_type=EvidenceSourceType.POLICY,
            policy_identifier="",
            explanation="Test explanation"
        )

def test_empty_explanation_rejected():
    with pytest.raises(ValidationError):
        RiskAssessmentEvidence(
            source_type=EvidenceSourceType.POLICY,
            policy_identifier="rule_123",
            explanation=""
        )

def test_event_ids_preserved():
    evidence = RiskAssessmentEvidence(
        source_type=EvidenceSourceType.POLICY,
        policy_identifier="rule_123",
        contributing_event_ids=["e1", "e2"],
        explanation="Test"
    )
    assert evidence.contributing_event_ids == ["e1", "e2"]

def test_event_types_preserved():
    evidence = RiskAssessmentEvidence(
        source_type=EvidenceSourceType.POLICY,
        policy_identifier="rule_123",
        contributing_event_types=[EventType.LOITERING],
        explanation="Test"
    )
    assert evidence.contributing_event_types == [EventType.LOITERING]

def test_optional_details_work():
    evidence = RiskAssessmentEvidence(
        source_type=EvidenceSourceType.POLICY,
        policy_identifier="rule_123",
        explanation="Test",
        details={"val": 100}
    )
    assert evidence.details["val"] == 100

def test_no_numeric_risk_score_field_exists():
    evidence = RiskAssessmentEvidence(
        source_type=EvidenceSourceType.POLICY,
        policy_identifier="rule_123",
        explanation="Test"
    )
    assert not hasattr(evidence, "score")
    assert not hasattr(evidence, "risk_score")

def test_evidence_defaults_to_none():
    assessment = RiskAssessment(
        event_id="e1",
        risk_level=RiskLevel.LOW,
        priority=Priority.LOW,
        reason="reason"
    )
    assert assessment.evidence is None

def test_existing_construction_remains_compatible():
    assessment = RiskAssessment(
        event_id="e1",
        risk_level=RiskLevel.LOW,
        priority=Priority.LOW,
        reason="reason"
    )
    assert assessment.event_id == "e1"

def test_evidence_can_be_attached():
    evidence = RiskAssessmentEvidence(
        source_type=EvidenceSourceType.POLICY,
        policy_identifier="rule_123",
        explanation="Test"
    )
    assessment = RiskAssessment(
        event_id="e1",
        risk_level=RiskLevel.LOW,
        priority=Priority.LOW,
        reason="reason",
        evidence=evidence
    )
    assert assessment.evidence is not None

def test_evidence_survives_open_to_acknowledged():
    evidence = RiskAssessmentEvidence(source_type=EvidenceSourceType.POLICY, policy_identifier="rule_123", explanation="Test")
    assessment = RiskAssessment(event_id="e1", risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="reason", evidence=evidence)
    assessment.transition_to(RiskAssessmentStatus.ACKNOWLEDGED)
    assert assessment.evidence == evidence

def test_evidence_survives_acknowledged_to_resolved():
    evidence = RiskAssessmentEvidence(source_type=EvidenceSourceType.POLICY, policy_identifier="rule_123", explanation="Test")
    assessment = RiskAssessment(event_id="e1", risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="reason", evidence=evidence, status=RiskAssessmentStatus.ACKNOWLEDGED)
    assessment.transition_to(RiskAssessmentStatus.RESOLVED)
    assert assessment.evidence == evidence

def test_transition_to_does_not_modify_evidence():
    evidence = RiskAssessmentEvidence(source_type=EvidenceSourceType.POLICY, policy_identifier="rule_123", explanation="Test", details={"x": 1})
    assessment = RiskAssessment(event_id="e1", risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="reason", evidence=evidence)
    assessment.transition_to(RiskAssessmentStatus.ACKNOWLEDGED)
    assert assessment.evidence.details == {"x": 1}

def test_policy_generated_assessment_contains_evidence():
    engine = RiskPolicyEngine(RiskPolicy.default())
    event = create_event(EventType.LOITERING, "e1")
    assessments = engine.assess_events([event])
    assert assessments[0].evidence is not None

def test_source_type_is_policy():
    engine = RiskPolicyEngine(RiskPolicy.default())
    event = create_event(EventType.LOITERING, "e1")
    assessments = engine.assess_events([event])
    assert assessments[0].evidence.source_type == EvidenceSourceType.POLICY

def test_policy_identifier_is_deterministic():
    engine = RiskPolicyEngine(RiskPolicy.default())
    event1 = create_event(EventType.LOITERING, "e1")
    event2 = create_event(EventType.LOITERING, "e2")
    assessments1 = engine.assess_events([event1])
    assessments2 = engine.assess_events([event2])
    assert assessments1[0].evidence.policy_identifier == assessments2[0].evidence.policy_identifier

def test_correct_event_id_is_included():
    engine = RiskPolicyEngine(RiskPolicy.default())
    event = create_event(EventType.LOITERING, "e1")
    assessments = engine.assess_events([event])
    assert "e1" in assessments[0].evidence.contributing_event_ids

def test_correct_event_type_is_included():
    engine = RiskPolicyEngine(RiskPolicy.default())
    event = create_event(EventType.LOITERING, "e1")
    assessments = engine.assess_events([event])
    assert EventType.LOITERING in assessments[0].evidence.contributing_event_types

def test_explanation_is_policy_based():
    engine = RiskPolicyEngine(RiskPolicy.default())
    event = create_event(EventType.LOITERING, "e1")
    assessments = engine.assess_events([event])
    assert "Configured policy rule assigned" in assessments[0].evidence.explanation

def test_correlated_assessment_contains_evidence():
    engine = RiskCorrelationEngine(RiskCorrelationPolicy.default())
    e1 = create_event(EventType.ZONE_ENTRY, "e1")
    e2 = create_event(EventType.LOITERING, "e2")
    assessments = engine.correlate([e1, e2])
    assert len(assessments) == 1
    assert assessments[0].evidence is not None

def test_source_type_is_correlation():
    engine = RiskCorrelationEngine(RiskCorrelationPolicy.default())
    e1 = create_event(EventType.ZONE_ENTRY, "e1")
    e2 = create_event(EventType.LOITERING, "e2")
    assessments = engine.correlate([e1, e2])
    assert assessments[0].evidence.source_type == EvidenceSourceType.CORRELATION

def test_correct_policy_identifier_is_present_correlation():
    engine = RiskCorrelationEngine(RiskCorrelationPolicy.default())
    e1 = create_event(EventType.ZONE_ENTRY, "e1")
    e2 = create_event(EventType.LOITERING, "e2")
    assessments = engine.correlate([e1, e2])
    assert len(assessments[0].evidence.policy_identifier) > 0

def test_all_contributing_event_ids_are_present():
    engine = RiskCorrelationEngine(RiskCorrelationPolicy.default())
    e1 = create_event(EventType.ZONE_ENTRY, "e1")
    e2 = create_event(EventType.LOITERING, "e2")
    assessments = engine.correlate([e1, e2])
    assert "e1" in assessments[0].evidence.contributing_event_ids
    assert "e2" in assessments[0].evidence.contributing_event_ids

def test_all_contributing_event_types_are_present():
    engine = RiskCorrelationEngine(RiskCorrelationPolicy.default())
    e1 = create_event(EventType.ZONE_ENTRY, "e1")
    e2 = create_event(EventType.LOITERING, "e2")
    assessments = engine.correlate([e1, e2])
    assert EventType.ZONE_ENTRY in assessments[0].evidence.contributing_event_types
    assert EventType.LOITERING in assessments[0].evidence.contributing_event_types

def test_explanation_describes_configured_correlation():
    engine = RiskCorrelationEngine(RiskCorrelationPolicy.default())
    e1 = create_event(EventType.ZONE_ENTRY, "e1")
    e2 = create_event(EventType.LOITERING, "e2")
    assessments = engine.correlate([e1, e2])
    assert "Configured correlation policy matched" in assessments[0].evidence.explanation

def test_escalated_assessment_contains_escalation_evidence():
    rule = RiskEscalationRule(source_risk_level=RiskLevel.HIGH, source_priority=Priority.HIGH, required_event_types=frozenset([EventType.LOITERING]), correlation_window_seconds=10, minimum_occurrences=2, target_risk_level=RiskLevel.CRITICAL, target_priority=Priority.CRITICAL, reason_template="escalated")
    engine = RiskEscalationEngine(RiskEscalationPolicy(rules=[rule]), RiskDeescalationPolicy(rules=[]))
    assessment = RiskAssessment(event_id="a1", contributing_event_ids=["e1"], contributing_event_types=[EventType.LOITERING], risk_level=RiskLevel.HIGH, priority=Priority.HIGH, reason="test")
    e1 = create_event(EventType.LOITERING, "e1", timestamp=1)
    e2 = create_event(EventType.LOITERING, "e2", timestamp=2)
    assessments = engine.evaluate([assessment], [e1, e2])
    assert assessments[0].evidence is not None
    assert assessments[0].evidence.source_type == EvidenceSourceType.ESCALATION

def test_deescalated_assessment_contains_deescalation_evidence():
    rule = RiskDeescalationRule(source_risk_level=RiskLevel.HIGH, source_priority=Priority.HIGH, absence_event_types=frozenset([EventType.LOITERING]), quiet_period_seconds=10, target_risk_level=RiskLevel.LOW, target_priority=Priority.LOW, reason_template="deescalated")
    engine = RiskEscalationEngine(RiskEscalationPolicy(rules=[]), RiskDeescalationPolicy(rules=[rule]))
    assessment = RiskAssessment(event_id="a1", contributing_event_ids=["e1"], contributing_event_types=[EventType.LOITERING], risk_level=RiskLevel.HIGH, priority=Priority.HIGH, reason="test")
    e1 = create_event(EventType.LOITERING, "e1", timestamp=1)
    e2 = create_event(EventType.ZONE_ENTRY, "e2", timestamp=12)
    assessments = engine.evaluate([assessment], [e1, e2])
    assert assessments[0].evidence is not None
    assert assessments[0].evidence.source_type == EvidenceSourceType.DEESCALATION

def test_policy_identifiers_are_deterministic_escalation():
    rule = RiskEscalationRule(source_risk_level=RiskLevel.HIGH, source_priority=Priority.HIGH, required_event_types=frozenset([EventType.LOITERING]), correlation_window_seconds=10, minimum_occurrences=2, target_risk_level=RiskLevel.CRITICAL, target_priority=Priority.CRITICAL, reason_template="escalated")
    engine = RiskEscalationEngine(RiskEscalationPolicy(rules=[rule]), RiskDeescalationPolicy(rules=[]))
    assessment = RiskAssessment(event_id="a1", contributing_event_ids=["e1"], contributing_event_types=[EventType.LOITERING], risk_level=RiskLevel.HIGH, priority=Priority.HIGH, reason="test")
    e1 = create_event(EventType.LOITERING, "e1", timestamp=1)
    e2 = create_event(EventType.LOITERING, "e2", timestamp=2)
    assessments1 = engine.evaluate([assessment], [e1, e2])
    assessments2 = engine.evaluate([assessment], [e1, e2])
    assert assessments1[0].evidence.policy_identifier == assessments2[0].evidence.policy_identifier

def test_source_traceability_is_preserved_escalation():
    rule = RiskEscalationRule(source_risk_level=RiskLevel.HIGH, source_priority=Priority.HIGH, required_event_types=frozenset([EventType.LOITERING]), correlation_window_seconds=10, minimum_occurrences=2, target_risk_level=RiskLevel.CRITICAL, target_priority=Priority.CRITICAL, reason_template="escalated")
    engine = RiskEscalationEngine(RiskEscalationPolicy(rules=[rule]), RiskDeescalationPolicy(rules=[]))
    assessment = RiskAssessment(event_id="a1", contributing_event_ids=["e1"], contributing_event_types=[EventType.LOITERING], risk_level=RiskLevel.HIGH, priority=Priority.HIGH, reason="test")
    e1 = create_event(EventType.LOITERING, "e1", timestamp=1)
    e2 = create_event(EventType.LOITERING, "e2", timestamp=2)
    assessments = engine.evaluate([assessment], [e1, e2])
    assert assessments[0].contributing_event_ids == ["e1"]

def test_explanation_is_factual_and_policy_based():
    rule = RiskEscalationRule(source_risk_level=RiskLevel.HIGH, source_priority=Priority.HIGH, required_event_types=frozenset([EventType.LOITERING]), correlation_window_seconds=10, minimum_occurrences=2, target_risk_level=RiskLevel.CRITICAL, target_priority=Priority.CRITICAL, reason_template="escalated")
    engine = RiskEscalationEngine(RiskEscalationPolicy(rules=[rule]), RiskDeescalationPolicy(rules=[]))
    assessment = RiskAssessment(event_id="a1", contributing_event_ids=["e1"], contributing_event_types=[EventType.LOITERING], risk_level=RiskLevel.HIGH, priority=Priority.HIGH, reason="test")
    e1 = create_event(EventType.LOITERING, "e1", timestamp=1)
    e2 = create_event(EventType.LOITERING, "e2", timestamp=2)
    assessments = engine.evaluate([assessment], [e1, e2])
    assert "Configured escalation policy pattern occurred" in assessments[0].evidence.explanation

def test_evidence_does_not_affect_identity():
    engine = RiskDeduplicationEngine(RiskDeduplicationPolicy())
    evidence1 = RiskAssessmentEvidence(source_type=EvidenceSourceType.POLICY, policy_identifier="r1", explanation="1")
    evidence2 = RiskAssessmentEvidence(source_type=EvidenceSourceType.POLICY, policy_identifier="r2", explanation="2")
    a1 = RiskAssessment(event_id="e1", risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="test", evidence=evidence1)
    a2 = RiskAssessment(event_id="e1", risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="test", evidence=evidence2)
    assert engine._calculate_identity(a1) == engine._calculate_identity(a2)

def test_different_evidence_wording_does_not_create_new_identity():
    engine = RiskDeduplicationEngine(RiskDeduplicationPolicy())
    evidence1 = RiskAssessmentEvidence(source_type=EvidenceSourceType.POLICY, policy_identifier="r1", explanation="word A")
    evidence2 = RiskAssessmentEvidence(source_type=EvidenceSourceType.POLICY, policy_identifier="r1", explanation="word B")
    a1 = RiskAssessment(event_id="e1", risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="test", evidence=evidence1)
    a2 = RiskAssessment(event_id="e1", risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="test", evidence=evidence2)
    res = engine.deduplicate([a1, a2])
    assert len(res) == 1

def test_same_logical_assessment_with_different_evidence_metadata_remains_deduplicated():
    engine = RiskDeduplicationEngine(RiskDeduplicationPolicy())
    evidence1 = RiskAssessmentEvidence(source_type=EvidenceSourceType.POLICY, policy_identifier="r1", explanation="word A", details={"d": 1})
    evidence2 = RiskAssessmentEvidence(source_type=EvidenceSourceType.POLICY, policy_identifier="r1", explanation="word A", details={"d": 2})
    a1 = RiskAssessment(event_id="e1", risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="test", evidence=evidence1)
    a2 = RiskAssessment(event_id="e1", risk_level=RiskLevel.LOW, priority=Priority.LOW, reason="test", evidence=evidence2)
    res = engine.deduplicate([a1, a2])
    assert len(res) == 1

def test_same_policy_produces_same_policy_identifier():
    policy = RiskPolicy.default()
    engine1 = RiskPolicyEngine(policy)
    engine2 = RiskPolicyEngine(policy)
    e1 = create_event(EventType.LOITERING, "e1")
    e2 = create_event(EventType.LOITERING, "e2")
    assert engine1.assess_events([e1])[0].evidence.policy_identifier == engine2.assess_events([e2])[0].evidence.policy_identifier

def test_same_correlation_rule_produces_same_identifier():
    rule = RiskCorrelationRule(event_types=frozenset([EventType.ZONE_ENTRY, EventType.LOITERING]), risk_level=RiskLevel.HIGH, priority=Priority.HIGH, reason_template="r")
    engine1 = RiskCorrelationEngine(RiskCorrelationPolicy(rules=[rule]))
    engine2 = RiskCorrelationEngine(RiskCorrelationPolicy(rules=[rule]))
    e1 = create_event(EventType.ZONE_ENTRY, "e1")
    e2 = create_event(EventType.LOITERING, "e2")
    e3 = create_event(EventType.ZONE_ENTRY, "e3")
    e4 = create_event(EventType.LOITERING, "e4")
    a1 = engine1.correlate([e1, e2])
    a2 = engine2.correlate([e3, e4])
    assert a1[0].evidence.policy_identifier == a2[0].evidence.policy_identifier

def test_same_escalation_rule_produces_same_identifier():
    rule = RiskEscalationRule(source_risk_level=RiskLevel.HIGH, source_priority=Priority.HIGH, required_event_types=frozenset([EventType.LOITERING]), correlation_window_seconds=10, minimum_occurrences=2, target_risk_level=RiskLevel.CRITICAL, target_priority=Priority.CRITICAL, reason_template="escalated")
    engine = RiskEscalationEngine(RiskEscalationPolicy(rules=[rule]), RiskDeescalationPolicy(rules=[]))
    assessment1 = RiskAssessment(event_id="a1", contributing_event_ids=["e1"], contributing_event_types=[EventType.LOITERING], risk_level=RiskLevel.HIGH, priority=Priority.HIGH, reason="test")
    assessment2 = RiskAssessment(event_id="a2", contributing_event_ids=["e3"], contributing_event_types=[EventType.LOITERING], risk_level=RiskLevel.HIGH, priority=Priority.HIGH, reason="test")
    e1 = create_event(EventType.LOITERING, "e1", timestamp=1)
    e2 = create_event(EventType.LOITERING, "e2", timestamp=2)
    e3 = create_event(EventType.LOITERING, "e3", timestamp=1)
    e4 = create_event(EventType.LOITERING, "e4", timestamp=2)
    a1 = engine.evaluate([assessment1], [e1, e2])
    a2 = engine.evaluate([assessment2], [e3, e4])
    assert a1[0].evidence.policy_identifier == a2[0].evidence.policy_identifier

def test_repeated_engine_calls_produce_equivalent_evidence():
    engine = RiskPolicyEngine(RiskPolicy.default())
    event = create_event(EventType.LOITERING, "e1")
    a1 = engine.assess_events([event])[0]
    a2 = engine.assess_events([event])[0]
    assert a1.evidence.model_dump() == a2.evidence.model_dump()

def test_evidence_does_not_contain_criminality_classification():
    evidence = RiskAssessmentEvidence(source_type=EvidenceSourceType.POLICY, policy_identifier="rule_123", explanation="Test")
    assert "criminal" not in evidence.explanation.lower()
    assert "guilt" not in evidence.explanation.lower()

def test_evidence_does_not_contain_intent_classification():
    evidence = RiskAssessmentEvidence(source_type=EvidenceSourceType.POLICY, policy_identifier="rule_123", explanation="Test")
    assert "intent" not in evidence.explanation.lower()

def test_evidence_does_not_contain_autonomous_enforcement_instruction():
    evidence = RiskAssessmentEvidence(source_type=EvidenceSourceType.POLICY, policy_identifier="rule_123", explanation="Test")
    assert "enforcement" not in evidence.explanation.lower()
    assert "automatic" not in evidence.explanation.lower()

def test_no_numeric_risk_score_is_generated():
    engine = RiskPolicyEngine(RiskPolicy.default())
    event = create_event(EventType.LOITERING, "e1")
    assessments = engine.assess_events([event])
    assert "score" not in assessments[0].model_dump()
    assert "risk_score" not in assessments[0].model_dump()
