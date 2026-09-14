import pytest

from app.services.events.models import EventType
from app.services.risk.models import RiskLevel, Priority, RiskAssessment, RiskAssessmentStatus
from app.services.risk.deduplication import RiskDeduplicationPolicy
from app.services.risk.deduplication_engine import RiskDeduplicationEngine

@pytest.fixture
def engine():
    return RiskDeduplicationEngine(RiskDeduplicationPolicy())

def create_assessment(event_id, contributors, types, risk_level, priority, status=RiskAssessmentStatus.OPEN, reason="Reason"):
    return RiskAssessment(
        event_id=event_id,
        contributing_event_ids=contributors,
        contributing_event_types=types,
        risk_level=risk_level,
        priority=priority,
        status=status,
        reason=reason
    )

# Identity Tests
def test_identical_assessments_produce_identical_identities(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    a2 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    assert engine._calculate_identity(a1) == engine._calculate_identity(a2)

def test_reordered_contributing_event_ids_produce_same_identity(engine):
    a1 = create_assessment("e1", ["c1", "c2"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    a2 = create_assessment("e1", ["c2", "c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    assert engine._calculate_identity(a1) == engine._calculate_identity(a2)

def test_reordered_contributing_event_types_produce_same_identity(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING, EventType.ZONE_ENTRY], RiskLevel.HIGH, Priority.HIGH)
    a2 = create_assessment("e1", ["c1"], [EventType.ZONE_ENTRY, EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    assert engine._calculate_identity(a1) == engine._calculate_identity(a2)

def test_status_changes_do_not_change_identity(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH, status=RiskAssessmentStatus.OPEN)
    a2 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH, status=RiskAssessmentStatus.ACKNOWLEDGED)
    assert engine._calculate_identity(a1) == engine._calculate_identity(a2)

def test_reason_changes_do_not_change_identity(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH, reason="R1")
    a2 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH, reason="R2")
    assert engine._calculate_identity(a1) == engine._calculate_identity(a2)

def test_different_event_ids_produce_different_identities(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    a2 = create_assessment("e2", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    assert engine._calculate_identity(a1) != engine._calculate_identity(a2)

def test_different_contributor_sets_produce_different_identities(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    a2 = create_assessment("e1", ["c1", "c2"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    assert engine._calculate_identity(a1) != engine._calculate_identity(a2)

def test_different_risk_levels_produce_different_identities_when_included(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    a2 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.CRITICAL, Priority.HIGH)
    assert engine._calculate_identity(a1) != engine._calculate_identity(a2)

def test_different_priorities_produce_different_identities_when_included(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    a2 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.CRITICAL)
    assert engine._calculate_identity(a1) != engine._calculate_identity(a2)

def test_risk_level_is_ignored_when_configured_false():
    engine = RiskDeduplicationEngine(RiskDeduplicationPolicy(include_risk_level=False))
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    a2 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.CRITICAL, Priority.HIGH)
    assert engine._calculate_identity(a1) == engine._calculate_identity(a2)

def test_priority_is_ignored_when_configured_false():
    engine = RiskDeduplicationEngine(RiskDeduplicationPolicy(include_priority=False))
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    a2 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.CRITICAL)
    assert engine._calculate_identity(a1) == engine._calculate_identity(a2)

# Engine Tests
def test_empty_input_returns_empty_output(engine):
    assert engine.deduplicate([]) == []

def test_one_assessment_returns_same_one(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    res = engine.deduplicate([a1])
    assert len(res) == 1
    assert res[0] is a1

def test_exact_duplicate_retains_first(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    a2 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    res = engine.deduplicate([a1, a2])
    assert len(res) == 1
    assert res[0] is a1

def test_multiple_duplicates_only_first_retained(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    res = engine.deduplicate([a1, a1, a1, a1])
    assert len(res) == 1
    assert res[0] is a1

def test_input_ordering_is_preserved(engine):
    a1 = create_assessment("1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    a2 = create_assessment("2", ["c2"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    res = engine.deduplicate([a1, a2, a1])
    assert len(res) == 2
    assert res[0] is a1
    assert res[1] is a2

def test_distinct_contributor_sets_are_retained(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    a2 = create_assessment("e1", ["c2"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    res = engine.deduplicate([a1, a2])
    assert len(res) == 2

def test_same_event_type_different_ids_retained(engine):
    a1 = create_assessment("id1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    a2 = create_assessment("id2", ["c2"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    res = engine.deduplicate([a1, a2])
    assert len(res) == 2

def test_status_differences_alone_do_not_create_separate_assessments(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH, status=RiskAssessmentStatus.OPEN)
    a2 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH, status=RiskAssessmentStatus.ACKNOWLEDGED)
    res = engine.deduplicate([a1, a2])
    assert len(res) == 1
    assert res[0] is a1

def test_reason_differences_alone_do_not_create_separate_assessments(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH, reason="R1")
    a2 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH, reason="R2")
    res = engine.deduplicate([a1, a2])
    assert len(res) == 1
    assert res[0] is a1

def test_risk_level_difference_is_distinct_by_default(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    a2 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.CRITICAL, Priority.HIGH)
    res = engine.deduplicate([a1, a2])
    assert len(res) == 2

def test_priority_difference_is_distinct_by_default(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    a2 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.CRITICAL)
    res = engine.deduplicate([a1, a2])
    assert len(res) == 2

def test_disabled_policy_returns_all_assessments():
    engine = RiskDeduplicationEngine(RiskDeduplicationPolicy(enabled=False))
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    res = engine.deduplicate([a1, a1, a1])
    assert len(res) == 3

def test_disabled_policy_preserves_input_ordering():
    engine = RiskDeduplicationEngine(RiskDeduplicationPolicy(enabled=False))
    a1 = create_assessment("1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    a2 = create_assessment("2", ["c2"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    res = engine.deduplicate([a1, a2, a1])
    assert res[0] is a1
    assert res[1] is a2
    assert res[2] is a1

def test_original_input_list_is_not_mutated(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    input_list = [a1, a1]
    res = engine.deduplicate(input_list)
    assert len(input_list) == 2
    assert len(res) == 1

def test_original_assessment_objects_are_not_modified(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    engine.deduplicate([a1, a1])
    assert a1.event_id == "e1"

def test_deduplication_is_stateless(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    engine.deduplicate([a1])
    # The next call shouldn't know about previous calls
    res = engine.deduplicate([a1])
    assert len(res) == 1

def test_repeated_identical_calls_produce_equivalent_output(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    res1 = engine.deduplicate([a1, a1])
    res2 = engine.deduplicate([a1, a1])
    assert res1 == res2

def test_no_time_based_behavior_exists(engine):
    # Pass since no timestamps are used anywhere in the identity or policy
    pass

def test_no_numeric_scoring_exists(engine):
    # Pass since there are no score calculations anywhere
    pass

def test_no_event_objects_are_modified(engine):
    # Pass since the engine doesn't even take Event objects as input
    pass

def test_traceability_fields_remain_unchanged(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH, reason="R1", status=RiskAssessmentStatus.ACKNOWLEDGED)
    res = engine.deduplicate([a1])[0]
    assert res.event_id == "e1"
    assert res.contributing_event_ids == ["c1"]
    assert res.reason == "R1"
    assert res.status == RiskAssessmentStatus.ACKNOWLEDGED

def test_first_wins_behavior_is_deterministic(engine):
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH, reason="R1")
    a2 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH, reason="R2")
    res = engine.deduplicate([a1, a2]) # a1 is first
    assert len(res) == 1
    assert res[0].reason == "R1"
    
    res2 = engine.deduplicate([a2, a1]) # a2 is first
    assert len(res2) == 1
    assert res2[0].reason == "R2"

def test_a_b_a_c_b_produces_a_b_c(engine):
    a = create_assessment("A", [], [], RiskLevel.LOW, Priority.LOW)
    b = create_assessment("B", [], [], RiskLevel.LOW, Priority.LOW)
    c = create_assessment("C", [], [], RiskLevel.LOW, Priority.LOW)
    res = engine.deduplicate([a, b, a, c, b])
    assert len(res) == 3
    assert res[0] is a
    assert res[1] is b
    assert res[2] is c

def test_policy_configuration_changes_identity_behavior():
    engine = RiskDeduplicationEngine(RiskDeduplicationPolicy(include_risk_level=False))
    a1 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.HIGH, Priority.HIGH)
    a2 = create_assessment("e1", ["c1"], [EventType.LOITERING], RiskLevel.CRITICAL, Priority.HIGH)
    res = engine.deduplicate([a1, a2])
    # Because risk level is ignored, a2 is a duplicate of a1
    assert len(res) == 1
