import pytest
from pydantic import ValidationError

from app.services.events.models import EventType
from app.services.risk.models import RiskLevel, Priority
from app.services.risk.correlation import RiskCorrelationRule, RiskCorrelationPolicy

def test_valid_risk_correlation_rule_construction():
    rule = RiskCorrelationRule(
        event_types=frozenset([EventType.ZONE_ENTRY, EventType.LOITERING]),
        risk_level=RiskLevel.HIGH,
        priority=Priority.HIGH,
        reason_template="Test"
    )
    assert len(rule.event_types) == 2
    assert rule.risk_level == RiskLevel.HIGH

def test_valid_event_type_values_accepted():
    rule = RiskCorrelationRule(
        event_types=frozenset([EventType.TRACK_STARTED, EventType.TRACK_ENDED]),
        risk_level=RiskLevel.LOW,
        priority=Priority.LOW,
        reason_template="Test"
    )
    assert EventType.TRACK_STARTED in rule.event_types

def test_invalid_risk_level_rejected():
    with pytest.raises(ValidationError):
        RiskCorrelationRule(
            event_types=frozenset([EventType.ZONE_ENTRY, EventType.LOITERING]),
            risk_level="INVALID",
            priority=Priority.HIGH,
            reason_template="Test"
        )

def test_invalid_priority_rejected():
    with pytest.raises(ValidationError):
        RiskCorrelationRule(
            event_types=frozenset([EventType.ZONE_ENTRY, EventType.LOITERING]),
            risk_level=RiskLevel.HIGH,
            priority="INVALID",
            reason_template="Test"
        )

def test_empty_reason_template_rejected():
    with pytest.raises(ValidationError):
        RiskCorrelationRule(
            event_types=frozenset([EventType.ZONE_ENTRY, EventType.LOITERING]),
            risk_level=RiskLevel.HIGH,
            priority=Priority.HIGH,
            reason_template=""
        )

def test_less_than_two_event_types_rejected():
    with pytest.raises(ValidationError, match="requires at least two distinct"):
        RiskCorrelationRule(
            event_types=frozenset([EventType.ZONE_ENTRY]),
            risk_level=RiskLevel.HIGH,
            priority=Priority.HIGH,
            reason_template="Test"
        )

def test_duplicate_event_types_rejected():
    # FrozenSet automatically drops duplicates, so attempting [LOITERING, LOITERING] results in len 1,
    # which fails the minimum 2 requirement.
    with pytest.raises(ValidationError, match="requires at least two distinct"):
        RiskCorrelationRule(
            event_types=frozenset([EventType.LOITERING, EventType.LOITERING]),
            risk_level=RiskLevel.HIGH,
            priority=Priority.HIGH,
            reason_template="Test"
        )

def test_default_policy_constructs_successfully():
    policy = RiskCorrelationPolicy.default()
    assert policy is not None

def test_default_policy_contains_expected_rules():
    policy = RiskCorrelationPolicy.default()
    assert len(policy.rules) == 4
    types = [rule.event_types for rule in policy.rules]
    assert frozenset([EventType.ZONE_ENTRY, EventType.LOITERING]) in types
    assert frozenset([EventType.ZONE_ENTRY, EventType.RAPID_MOVEMENT]) in types
    assert frozenset([EventType.RAPID_MOVEMENT, EventType.DIRECTION_CHANGE]) in types
    assert frozenset([EventType.MULTIPLE_OBJECT_PROXIMITY, EventType.LOITERING]) in types

def test_every_rule_has_valid_fields():
    policy = RiskCorrelationPolicy.default()
    for rule in policy.rules:
        assert isinstance(rule.risk_level, RiskLevel)
        assert isinstance(rule.priority, Priority)
        assert len(rule.reason_template) > 0

def test_correlation_window_seconds_accepts_valid_value():
    policy = RiskCorrelationPolicy(correlation_window_seconds=60.0)
    assert policy.correlation_window_seconds == 60.0

def test_invalid_correlation_window_rejected():
    with pytest.raises(ValidationError):
        RiskCorrelationPolicy(correlation_window_seconds=0.0)
    with pytest.raises(ValidationError):
        RiskCorrelationPolicy(correlation_window_seconds=-10.0)

def test_explicit_custom_policy_constructed():
    custom_rule = RiskCorrelationRule(
        event_types=frozenset([EventType.TRACK_STARTED, EventType.TRACK_ENDED]),
        risk_level=RiskLevel.CRITICAL,
        priority=Priority.CRITICAL,
        reason_template="Instant end"
    )
    policy = RiskCorrelationPolicy(rules=[custom_rule], correlation_window_seconds=15.0)
    assert len(policy.rules) == 1
    assert policy.correlation_window_seconds == 15.0
