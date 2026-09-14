import pytest

from app.services.events.models import Event, EventType
from app.services.risk.models import RiskLevel, Priority, RiskAssessment, RiskAssessmentStatus
from app.services.risk.escalation import RiskEscalationRule, RiskEscalationPolicy, RiskDeescalationRule, RiskDeescalationPolicy
from app.services.risk.escalation_engine import RiskEscalationEngine

@pytest.fixture
def engine():
    return RiskEscalationEngine()

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

def create_assessment(id_str: str, level: RiskLevel, contrib: list, status=RiskAssessmentStatus.OPEN) -> RiskAssessment:
    return RiskAssessment(
        event_id=id_str,
        contributing_event_ids=contrib,
        contributing_event_types=[EventType.LOITERING],
        risk_level=level,
        priority=Priority(level.value), # match priority for tests
        reason="Test",
        status=status
    )

def test_empty_assessments_no_output(engine):
    assert engine.evaluate([], []) == []

def test_no_matching_rule_no_modification(engine):
    ass = create_assessment("a1", RiskLevel.LOW, ["e1"])
    evt = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    res = engine.evaluate([ass], [evt])
    assert res[0].risk_level == RiskLevel.LOW

def test_matching_escalation_rule_produces_updated_assessment(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1)
    res = engine.evaluate([ass], [evt1, evt2])
    assert res[0].risk_level == RiskLevel.CRITICAL

def test_source_risk_level_mismatch_no_escalation(engine):
    ass = create_assessment("a1", RiskLevel.MEDIUM, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1)
    res = engine.evaluate([ass], [evt1, evt2])
    assert res[0].risk_level == RiskLevel.MEDIUM

def test_source_priority_mismatch_no_escalation(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    ass.priority = Priority.LOW # Mismatch
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1)
    res = engine.evaluate([ass], [evt1, evt2])
    assert res[0].risk_level == RiskLevel.HIGH

def test_required_event_type_missing_no_escalation(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.ZONE_ENTRY, 5.0, 1) # Not LOITERING
    res = engine.evaluate([ass], [evt1, evt2])
    assert res[0].risk_level == RiskLevel.HIGH

def test_minimum_occurrence_count_respected(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    # Only 1 occurrence, rule needs 2
    res = engine.evaluate([ass], [evt1])
    assert res[0].risk_level == RiskLevel.HIGH

def test_duplicate_event_ids_cannot_inflate_occurrence_count(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    # Sending e1 twice
    res = engine.evaluate([ass], [evt1, evt1])
    assert res[0].risk_level == RiskLevel.HIGH

def test_events_outside_temporal_window_do_not_escalate(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 65.0, 1) # Window is 60
    res = engine.evaluate([ass], [evt1, evt2])
    assert res[0].risk_level == RiskLevel.HIGH

def test_exact_temporal_boundary_does_escalate(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 61.0, 1) # 60 diff
    res = engine.evaluate([ass], [evt1, evt2])
    assert res[0].risk_level == RiskLevel.CRITICAL

def test_different_tracks_do_not_satisfy_one_escalation_pattern(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 2) # Track 2
    res = engine.evaluate([ass], [evt1, evt2])
    assert res[0].risk_level == RiskLevel.HIGH

def test_same_track_can_satisfy_recurrence(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1) 
    res = engine.evaluate([ass], [evt1, evt2])
    assert res[0].risk_level == RiskLevel.CRITICAL

def test_multiple_required_event_types_require_every_type():
    rule = RiskEscalationRule(
        source_risk_level=RiskLevel.HIGH,
        source_priority=Priority.HIGH,
        required_event_types=frozenset([EventType.ZONE_ENTRY, EventType.LOITERING]),
        minimum_occurrences=2,
        correlation_window_seconds=60.0,
        target_risk_level=RiskLevel.CRITICAL,
        target_priority=Priority.CRITICAL,
        reason_template="Test"
    )
    engine = RiskEscalationEngine(escalation_policy=RiskEscalationPolicy(rules=[rule]))
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1) 
    res = engine.evaluate([ass], [evt1, evt2])
    assert res[0].risk_level == RiskLevel.CRITICAL

def test_a_plus_a_does_not_satisfy_a_plus_b():
    rule = RiskEscalationRule(
        source_risk_level=RiskLevel.HIGH,
        source_priority=Priority.HIGH,
        required_event_types=frozenset([EventType.ZONE_ENTRY, EventType.LOITERING]),
        minimum_occurrences=2,
        correlation_window_seconds=60.0,
        target_risk_level=RiskLevel.CRITICAL,
        target_priority=Priority.CRITICAL,
        reason_template="Test"
    )
    engine = RiskEscalationEngine(escalation_policy=RiskEscalationPolicy(rules=[rule]))
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    evt2 = create_event("e2", EventType.ZONE_ENTRY, 5.0, 1) 
    res = engine.evaluate([ass], [evt1, evt2])
    assert res[0].risk_level == RiskLevel.HIGH

def test_escalation_preserves_contributing_event_ids(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1", "e_old"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1)
    res = engine.evaluate([ass], [evt1, evt2])[0]
    assert "e1" in res.contributing_event_ids
    assert "e_old" in res.contributing_event_ids

def test_escalation_preserves_contributing_event_types(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    ass.contributing_event_types = [EventType.ZONE_ENTRY] # Override to test preservation
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1)
    res = engine.evaluate([ass], [evt1, evt2])[0]
    assert EventType.ZONE_ENTRY in res.contributing_event_types

def test_escalation_preserves_assessment_status(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"], status=RiskAssessmentStatus.ACKNOWLEDGED)
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1)
    res = engine.evaluate([ass], [evt1, evt2])[0]
    assert res.status == RiskAssessmentStatus.ACKNOWLEDGED

def test_escalation_preserves_original_event_id(engine):
    ass = create_assessment("original-id-123", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1)
    res = engine.evaluate([ass], [evt1, evt2])[0]
    assert res.event_id == "original-id-123"

def test_escalation_reason_comes_from_configured_rule(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1)
    res = engine.evaluate([ass], [evt1, evt2])[0]
    assert "Configured policy escalates" in res.reason

def test_multiple_matching_escalation_rules_produce_deterministic_multiple_outputs():
    r1 = RiskEscalationRule(
        source_risk_level=RiskLevel.HIGH, source_priority=Priority.HIGH,
        required_event_types=frozenset([EventType.LOITERING]), minimum_occurrences=2,
        correlation_window_seconds=60.0, target_risk_level=RiskLevel.CRITICAL,
        target_priority=Priority.CRITICAL, reason_template="R1"
    )
    r2 = RiskEscalationRule(
        source_risk_level=RiskLevel.HIGH, source_priority=Priority.HIGH,
        required_event_types=frozenset([EventType.LOITERING]), minimum_occurrences=2,
        correlation_window_seconds=60.0, target_risk_level=RiskLevel.CRITICAL,
        target_priority=Priority.HIGH, reason_template="R2"
    )
    engine = RiskEscalationEngine(escalation_policy=RiskEscalationPolicy(rules=[r1, r2]))
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1)
    res = engine.evaluate([ass], [evt1, evt2])
    assert len(res) == 2
    assert res[0].reason == "R1"
    assert res[1].reason == "R2"

def test_rule_ordering_is_deterministic():
    r1 = RiskEscalationRule(
        source_risk_level=RiskLevel.HIGH, source_priority=Priority.HIGH,
        required_event_types=frozenset([EventType.LOITERING]), minimum_occurrences=2,
        correlation_window_seconds=60.0, target_risk_level=RiskLevel.CRITICAL,
        target_priority=Priority.CRITICAL, reason_template="R1"
    )
    r2 = RiskEscalationRule(
        source_risk_level=RiskLevel.HIGH, source_priority=Priority.HIGH,
        required_event_types=frozenset([EventType.LOITERING]), minimum_occurrences=2,
        correlation_window_seconds=60.0, target_risk_level=RiskLevel.CRITICAL,
        target_priority=Priority.HIGH, reason_template="R2"
    )
    # Reversing rule order in policy
    engine = RiskEscalationEngine(escalation_policy=RiskEscalationPolicy(rules=[r2, r1]))
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1)
    res = engine.evaluate([ass], [evt1, evt2])
    assert res[0].reason == "R2"
    assert res[1].reason == "R1"

def test_no_cascading_escalation_occurs_in_one_pass():
    # R1: HIGH->CRITICAL
    # R2: CRITICAL->CRITICAL with different reason
    r1 = RiskEscalationRule(
        source_risk_level=RiskLevel.HIGH, source_priority=Priority.HIGH,
        required_event_types=frozenset([EventType.LOITERING]), minimum_occurrences=2,
        correlation_window_seconds=60.0, target_risk_level=RiskLevel.CRITICAL,
        target_priority=Priority.CRITICAL, reason_template="R1"
    )
    r2 = RiskEscalationRule(
        source_risk_level=RiskLevel.CRITICAL, source_priority=Priority.CRITICAL,
        required_event_types=frozenset([EventType.LOITERING]), minimum_occurrences=2,
        correlation_window_seconds=60.0, target_risk_level=RiskLevel.CRITICAL,
        target_priority=Priority.CRITICAL, reason_template="R2"
    )
    engine = RiskEscalationEngine(escalation_policy=RiskEscalationPolicy(rules=[r1, r2]))
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1)
    res = engine.evaluate([ass], [evt1, evt2])
    # Should only produce R1 output. R2 shouldn't trigger on the newly produced CRITICAL
    assert len(res) == 1
    assert res[0].reason == "R1"

def test_matching_deescalation_rule_reduces_configured_level(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    # e1 at T=1.0. New event e2 at T=65.0. No LOITERING in between.
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.ZONE_EXIT, 65.0, 1)
    res = engine.evaluate([ass], [evt1, evt2])
    assert res[0].risk_level == RiskLevel.MEDIUM

def test_deescalation_requires_configured_quiet_period(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.ZONE_EXIT, 50.0, 1) # Less than 60s
    res = engine.evaluate([ass], [evt1, evt2])
    assert res[0].risk_level == RiskLevel.HIGH

def test_exact_quiet_period_boundary_works(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.ZONE_EXIT, 61.0, 1) # Exactly 60s
    res = engine.evaluate([ass], [evt1, evt2])
    assert res[0].risk_level == RiskLevel.MEDIUM

def test_empty_event_input_cannot_fabricate_quiet_period(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    # Empty event list
    res = engine.evaluate([ass], [])
    assert res[0].risk_level == RiskLevel.HIGH

def test_deescalation_preserves_assessment_status(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"], status=RiskAssessmentStatus.ACKNOWLEDGED)
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.ZONE_EXIT, 65.0, 1)
    res = engine.evaluate([ass], [evt1, evt2])[0]
    assert res.status == RiskAssessmentStatus.ACKNOWLEDGED

def test_deescalation_preserves_traceability(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.ZONE_EXIT, 65.0, 1)
    res = engine.evaluate([ass], [evt1, evt2])[0]
    assert res.event_id == "a1"
    assert "e1" in res.contributing_event_ids

def test_deescalation_reason_comes_from_configured_rule(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.ZONE_EXIT, 65.0, 1)
    res = engine.evaluate([ass], [evt1, evt2])[0]
    assert "de-escalates" in res.reason

def test_critical_is_not_implicitly_deescalated(engine):
    ass = create_assessment("a1", RiskLevel.CRITICAL, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.ZONE_EXIT, 65.0, 1)
    res = engine.evaluate([ass], [evt1, evt2])
    # De-esc rule applies to HIGH, not CRITICAL
    assert res[0].risk_level == RiskLevel.CRITICAL

def test_resolved_assessments_are_ignored(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"], status=RiskAssessmentStatus.RESOLVED)
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1) # Should escalate if not resolved
    res = engine.evaluate([ass], [evt1, evt2])
    assert res[0].risk_level == RiskLevel.HIGH
    
def test_escalation_takes_precedence_over_deescalation_when_both_match():
    # Create rule where event A absence triggers de-esc, but event B presence triggers esc
    esc_rule = RiskEscalationRule(
        source_risk_level=RiskLevel.HIGH, source_priority=Priority.HIGH,
        required_event_types=frozenset([EventType.ZONE_ENTRY]), minimum_occurrences=1,
        correlation_window_seconds=60.0, target_risk_level=RiskLevel.CRITICAL,
        target_priority=Priority.CRITICAL, reason_template="Esc"
    )
    deesc_rule = RiskDeescalationRule(
        source_risk_level=RiskLevel.HIGH, source_priority=Priority.HIGH,
        absence_event_types=frozenset([EventType.LOITERING]), quiet_period_seconds=60.0,
        target_risk_level=RiskLevel.MEDIUM, target_priority=Priority.MEDIUM, reason_template="Deesc"
    )
    engine = RiskEscalationEngine(RiskEscalationPolicy(rules=[esc_rule]), RiskDeescalationPolicy(rules=[deesc_rule]))
    
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.ZONE_ENTRY, 65.0, 1) # Triggers esc AND de-esc
    
    res = engine.evaluate([ass], [evt1, evt2])
    assert len(res) == 1
    assert res[0].risk_level == RiskLevel.CRITICAL # Escalation won
    
def test_engine_is_stateless(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1)
    res1 = engine.evaluate([ass], [evt1, evt2])
    res2 = engine.evaluate([ass], [evt1, evt2])
    assert res1[0].model_dump() == res2[0].model_dump()

def test_repeated_identical_calls_produce_equivalent_results(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1)
    res1 = engine.evaluate([ass], [evt1, evt2])[0]
    res2 = engine.evaluate([ass], [evt1, evt2])[0]
    assert res1.event_id == res2.event_id
    assert res1.risk_level == res2.risk_level

def test_custom_policies_alter_behavior():
    custom_esc = RiskEscalationRule(
        source_risk_level=RiskLevel.LOW, source_priority=Priority.LOW,
        required_event_types=frozenset([EventType.ZONE_ENTRY]), minimum_occurrences=1,
        correlation_window_seconds=60.0, target_risk_level=RiskLevel.HIGH,
        target_priority=Priority.HIGH, reason_template="Custom"
    )
    engine = RiskEscalationEngine(escalation_policy=RiskEscalationPolicy(rules=[custom_esc]))
    ass = create_assessment("a1", RiskLevel.LOW, ["e1"])
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    res = engine.evaluate([ass], [evt1])
    assert res[0].risk_level == RiskLevel.HIGH

def test_no_numeric_score_is_produced(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1)
    res = engine.evaluate([ass], [evt1, evt2])[0]
    assert not hasattr(res, "score")

def test_no_intent_criminality_classification_is_produced(engine):
    ass = create_assessment("a1", RiskLevel.HIGH, ["e1"])
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1)
    res = engine.evaluate([ass], [evt1, evt2])[0]
    reason = res.reason.lower()
    assert "criminal" not in reason
    assert "intent" not in reason
    assert "guilt" not in reason
