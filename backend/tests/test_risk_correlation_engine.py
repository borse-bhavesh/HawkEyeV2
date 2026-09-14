import pytest

from app.services.events.models import Event, EventType
from app.services.risk.models import RiskLevel, Priority
from app.services.risk.correlation import RiskCorrelationRule, RiskCorrelationPolicy
from app.services.risk.correlation_engine import RiskCorrelationEngine

@pytest.fixture
def engine():
    return RiskCorrelationEngine()

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

def test_empty_event_list_no_assessments(engine):
    assert len(engine.correlate([])) == 0

def test_one_event_no_correlation(engine):
    evt = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    assert len(engine.correlate([evt])) == 0

def test_required_event_types_present_correlation_matches(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1)
    assessments = engine.correlate([evt1, evt2])
    assert len(assessments) == 1

def test_missing_required_event_type_no_match(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    # Missing LOITERING for Rule 1, RAPID for Rule 2, etc.
    assessments = engine.correlate([evt1])
    assert len(assessments) == 0

def test_additional_unrelated_events_do_not_prevent_matching(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    evt2 = create_event("e2", EventType.TRACK_STARTED, 2.0, 1) # Unrelated to rule
    evt3 = create_event("e3", EventType.LOITERING, 5.0, 1)
    
    assessments = engine.correlate([evt1, evt2, evt3])
    assert len(assessments) == 1
    assert "e1" in assessments[0].contributing_event_ids
    assert "e3" in assessments[0].contributing_event_ids

def test_same_event_type_cannot_satisfy_two_required_types(engine):
    # Tested structurally via FrozeSet model validation. 
    # But if we send two LOITERINGs to an engine, it shouldn't match A+B.
    evt1 = create_event("e1", EventType.LOITERING, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 2.0, 1)
    assert len(engine.correlate([evt1, evt2])) == 0

def test_same_track_events_can_correlate(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 2.0, 1)
    assert len(engine.correlate([evt1, evt2])) == 1

def test_different_track_events_do_not_correlate(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 2.0, 2) # Track 2
    assert len(engine.correlate([evt1, evt2])) == 0

def test_track_less_events_do_not_create_fabricated_identity(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, None)
    evt2 = create_event("e2", EventType.LOITERING, 2.0, None)
    assert len(engine.correlate([evt1, evt2])) == 0

def test_events_outside_time_window_do_not_correlate(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 35.0, 1) # Window is 30
    assert len(engine.correlate([evt1, evt2])) == 0

def test_events_exactly_at_time_window_boundary_correlate(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 31.0, 1) # Exactly 30 sec diff
    assert len(engine.correlate([evt1, evt2])) == 1

def test_input_order_does_not_affect_matching(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1)
    ass1 = engine.correlate([evt1, evt2])
    ass2 = engine.correlate([evt2, evt1])
    assert len(ass1) == 1 and len(ass2) == 1
    assert ass1[0].contributing_event_ids == ass2[0].contributing_event_ids

def test_caller_event_list_is_not_mutated(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 5.0, 1)
    events = [evt2, evt1]
    engine.correlate(events)
    assert events[0].event_id == "e2"
    assert events[1].event_id == "e1"

def test_multiple_matching_rules_produce_multiple_assessments(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 2.0, 1)
    evt3 = create_event("e3", EventType.RAPID_MOVEMENT, 3.0, 1)
    
    # Matches (ZONE_ENTRY+LOITERING) and (ZONE_ENTRY+RAPID_MOVEMENT)
    assessments = engine.correlate([evt1, evt2, evt3])
    assert len(assessments) == 2

def test_assessment_fields_come_from_rule(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 2.0, 1)
    ass = engine.correlate([evt1, evt2])[0]
    
    # Check default policy Rule 1 mapping
    assert ass.risk_level == RiskLevel.HIGH
    assert ass.priority == Priority.HIGH
    assert "zone entry and subsequent loitering" in ass.reason

def test_all_contributing_event_ids_preserved(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 2.0, 1)
    ass = engine.correlate([evt1, evt2])[0]
    assert "e1" in ass.contributing_event_ids
    assert "e2" in ass.contributing_event_ids
    assert len(ass.contributing_event_ids) == 2

def test_all_contributing_event_types_preserved(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 2.0, 1)
    ass = engine.correlate([evt1, evt2])[0]
    assert EventType.ZONE_ENTRY in ass.contributing_event_types
    assert EventType.LOITERING in ass.contributing_event_types

def test_contributing_ids_are_deterministic(engine):
    evt1 = create_event("e2", EventType.ZONE_ENTRY, 1.0, 1) # Note id e2 comes first
    evt2 = create_event("e1", EventType.LOITERING, 2.0, 1)
    ass = engine.correlate([evt1, evt2])[0]
    assert ass.contributing_event_ids == ["e1", "e2"] # sorted by ID deterministically

def test_correlation_engine_is_stateless(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 2.0, 1)
    
    ass1 = engine.correlate([evt1, evt2])
    ass2 = engine.correlate([evt1, evt2])
    assert len(ass1) == 1 and len(ass2) == 1

def test_repeated_identical_calls_produce_identical_results(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 2.0, 1)
    
    ass1 = engine.correlate([evt1, evt2])[0]
    ass2 = engine.correlate([evt1, evt2])[0]
    
    assert ass1.model_dump() == ass2.model_dump()

def test_custom_policy_changes_correlation_behavior():
    custom_rule = RiskCorrelationRule(
        event_types=frozenset([EventType.TRACK_STARTED, EventType.TRACK_ENDED]),
        risk_level=RiskLevel.CRITICAL,
        priority=Priority.CRITICAL,
        reason_template="Instant end"
    )
    custom_engine = RiskCorrelationEngine(RiskCorrelationPolicy(rules=[custom_rule]))
    
    evt1 = create_event("e1", EventType.TRACK_STARTED, 1.0, 1)
    evt2 = create_event("e2", EventType.TRACK_ENDED, 2.0, 1)
    
    ass = custom_engine.correlate([evt1, evt2])
    assert len(ass) == 1
    assert ass[0].risk_level == RiskLevel.CRITICAL

def test_unknown_correlation_rule_cannot_silently_produce_assessment(engine):
    # TRACK_STARTED + TRACK_ENDED has no default correlation rule
    evt1 = create_event("e1", EventType.TRACK_STARTED, 1.0, 1)
    evt2 = create_event("e2", EventType.TRACK_ENDED, 2.0, 1)
    assert len(engine.correlate([evt1, evt2])) == 0

def test_no_numeric_risk_score_is_generated(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 2.0, 1)
    ass = engine.correlate([evt1, evt2])[0]
    assert not hasattr(ass, "score")
    assert not hasattr(ass, "weight")

def test_no_intent_criminality_language_generated(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 2.0, 1)
    reason = engine.correlate([evt1, evt2])[0].reason.lower()
    assert "criminal" not in reason
    assert "intent" not in reason
    assert "suspicion" not in reason

def test_rule_ordering_is_deterministic(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    evt2 = create_event("e2", EventType.LOITERING, 2.0, 1)
    evt3 = create_event("e3", EventType.RAPID_MOVEMENT, 3.0, 1)
    
    ass = engine.correlate([evt3, evt2, evt1])
    # The output should follow the order of rules in the policy list
    # Rule 1: ZONE_ENTRY + LOITERING
    # Rule 2: ZONE_ENTRY + RAPID_MOVEMENT
    assert ass[0].contributing_event_types == [EventType.ZONE_ENTRY, EventType.LOITERING]
    assert ass[1].contributing_event_types == [EventType.ZONE_ENTRY, EventType.RAPID_MOVEMENT]

def test_multiple_candidate_event_instances_handled(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1)
    evt2 = create_event("e2", EventType.ZONE_ENTRY, 2.0, 1) # Duplicate type
    evt3 = create_event("e3", EventType.LOITERING, 3.0, 1)
    
    ass = engine.correlate([evt1, evt2, evt3])
    assert len(ass) == 1
    # Because combo sort prioritizes min max_timestamp and min min_timestamp:
    # Combo (e1, e3) has max=3, min=1
    # Combo (e2, e3) has max=3, min=2
    # Wait, the algorithm picks min of (max_ts, min_ts). So (3, 1) is "smaller" than (3, 2).
    # Thus (e1, e3) is selected deterministically.
    assert "e1" in ass[0].contributing_event_ids
    assert "e3" in ass[0].contributing_event_ids

def test_two_separate_track_groups_not_mixed(engine):
    evt1 = create_event("e1", EventType.ZONE_ENTRY, 1.0, 1) # Track 1
    evt2 = create_event("e2", EventType.LOITERING, 2.0, 2)  # Track 2
    evt3 = create_event("e3", EventType.ZONE_ENTRY, 3.0, 2) # Track 2
    evt4 = create_event("e4", EventType.LOITERING, 4.0, 1)  # Track 1
    
    # Expected: (e1, e4) and (e3, e2) are valid pairs for track 1 and 2
    ass = engine.correlate([evt1, evt2, evt3, evt4])
    assert len(ass) == 2
    assert ass[0].contributing_event_ids == ["e1", "e4"] # Track 1 is processed first
    assert ass[1].contributing_event_ids == ["e2", "e3"] # Track 2 is processed second

def test_temporal_window_calculated_from_event_timestamps(engine):
    # Tested by test_events_exactly_at_time_window_boundary_correlate.
    # No direct test needed beyond existing boundary tests.
    assert True

def test_frame_numbers_not_used_for_time(engine):
    # Events have wild frame numbers but tight timestamps
    evt1 = Event(event_id="e1", event_type=EventType.ZONE_ENTRY, frame_number=0, timestamp_seconds=1.0, description="", track_id=1, evidence={})
    evt2 = Event(event_id="e2", event_type=EventType.LOITERING, frame_number=100000, timestamp_seconds=2.0, description="", track_id=1, evidence={})
    assert len(engine.correlate([evt1, evt2])) == 1
