import pytest
from pydantic import ValidationError

from app.services.events.models import EventType
from app.services.risk.models import RiskLevel, Priority
from app.services.risk.policy import RiskPolicy, RiskPolicyRule

def test_default_policy_can_be_constructed():
    policy = RiskPolicy.default()
    assert policy is not None
    assert len(policy.rules) > 0

def test_all_existing_event_types_covered():
    policy = RiskPolicy.default()
    for event_type in EventType:
        assert event_type in policy.rules

def test_track_started_has_valid_rule():
    policy = RiskPolicy.default()
    rule = policy.rules[EventType.TRACK_STARTED]
    assert rule.risk_level == RiskLevel.LOW

def test_track_ended_has_valid_rule():
    policy = RiskPolicy.default()
    rule = policy.rules[EventType.TRACK_ENDED]
    assert rule.risk_level == RiskLevel.LOW

def test_zone_entry_has_valid_rule():
    policy = RiskPolicy.default()
    rule = policy.rules[EventType.ZONE_ENTRY]
    assert rule.risk_level == RiskLevel.HIGH
    assert rule.priority == Priority.HIGH

def test_zone_exit_has_valid_rule():
    policy = RiskPolicy.default()
    rule = policy.rules[EventType.ZONE_EXIT]
    assert rule.risk_level == RiskLevel.LOW

def test_loitering_has_valid_rule():
    policy = RiskPolicy.default()
    rule = policy.rules[EventType.LOITERING]
    assert rule.risk_level == RiskLevel.HIGH

def test_rapid_movement_has_valid_rule():
    policy = RiskPolicy.default()
    rule = policy.rules[EventType.RAPID_MOVEMENT]
    assert rule.risk_level == RiskLevel.MEDIUM

def test_direction_change_has_valid_rule():
    policy = RiskPolicy.default()
    rule = policy.rules[EventType.DIRECTION_CHANGE]
    assert rule.risk_level == RiskLevel.MEDIUM

def test_multiple_object_proximity_has_valid_rule():
    policy = RiskPolicy.default()
    rule = policy.rules[EventType.MULTIPLE_OBJECT_PROXIMITY]
    assert rule.risk_level == RiskLevel.MEDIUM

def test_invalid_risk_level_rejected():
    with pytest.raises(ValidationError):
        RiskPolicyRule(risk_level="INVALID", priority=Priority.LOW, reason_template="Reason")

def test_invalid_priority_rejected():
    with pytest.raises(ValidationError):
        RiskPolicyRule(risk_level=RiskLevel.LOW, priority="INVALID", reason_template="Reason")

def test_empty_reason_template_rejected():
    with pytest.raises(ValidationError):
        RiskPolicyRule(risk_level=RiskLevel.LOW, priority=Priority.LOW, reason_template="")

def test_missing_required_event_type_rule_rejected():
    # Construct a dict missing one event type
    rules = RiskPolicy.default().rules
    del rules[EventType.LOITERING]
    with pytest.raises(ValueError, match="RiskPolicy is missing rules for EventTypes: \\['LOITERING'\\]"):
        RiskPolicy(rules=rules)

def test_explicit_policy_can_override_default():
    rules = RiskPolicy.default().rules
    rules[EventType.LOITERING] = RiskPolicyRule(
        risk_level=RiskLevel.LOW,
        priority=Priority.LOW,
        reason_template="Override"
    )
    policy = RiskPolicy(rules=rules)
    assert policy.rules[EventType.LOITERING].risk_level == RiskLevel.LOW

def test_policy_contains_no_numeric_risk_weight_requirement():
    # Evaluated by verifying RiskPolicyRule has no numeric fields
    rule = RiskPolicyRule(risk_level=RiskLevel.LOW, priority=Priority.LOW, reason_template="Test")
    assert not hasattr(rule, "score")
    assert not hasattr(rule, "weight")
