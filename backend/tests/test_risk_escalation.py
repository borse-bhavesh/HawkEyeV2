import pytest
from pydantic import ValidationError

from app.services.events.models import EventType
from app.services.risk.models import RiskLevel, Priority
from app.services.risk.escalation import (
    RiskEscalationRule,
    RiskEscalationPolicy,
    RiskDeescalationRule,
    RiskDeescalationPolicy
)

def test_valid_escalation_rule():
    rule = RiskEscalationRule(
        source_risk_level=RiskLevel.HIGH,
        source_priority=Priority.HIGH,
        required_event_types=frozenset([EventType.LOITERING]),
        minimum_occurrences=2,
        correlation_window_seconds=60.0,
        target_risk_level=RiskLevel.CRITICAL,
        target_priority=Priority.CRITICAL,
        reason_template="Test"
    )
    assert rule.minimum_occurrences == 2

def test_valid_deescalation_rule():
    rule = RiskDeescalationRule(
        source_risk_level=RiskLevel.HIGH,
        source_priority=Priority.HIGH,
        absence_event_types=frozenset([EventType.LOITERING]),
        quiet_period_seconds=60.0,
        target_risk_level=RiskLevel.MEDIUM,
        target_priority=Priority.MEDIUM,
        reason_template="Test"
    )
    assert rule.quiet_period_seconds == 60.0

def test_invalid_source_risk_level_rejected():
    with pytest.raises(ValidationError):
        RiskEscalationRule(
            source_risk_level="INVALID",
            source_priority=Priority.HIGH,
            required_event_types=frozenset([EventType.LOITERING]),
            minimum_occurrences=2,
            correlation_window_seconds=60.0,
            target_risk_level=RiskLevel.CRITICAL,
            target_priority=Priority.CRITICAL,
            reason_template="Test"
        )

def test_invalid_priority_rejected():
    with pytest.raises(ValidationError):
        RiskEscalationRule(
            source_risk_level=RiskLevel.HIGH,
            source_priority="INVALID",
            required_event_types=frozenset([EventType.LOITERING]),
            minimum_occurrences=2,
            correlation_window_seconds=60.0,
            target_risk_level=RiskLevel.CRITICAL,
            target_priority=Priority.CRITICAL,
            reason_template="Test"
        )

def test_empty_required_event_types_rejected():
    with pytest.raises(ValidationError):
        RiskEscalationRule(
            source_risk_level=RiskLevel.HIGH,
            source_priority=Priority.HIGH,
            required_event_types=frozenset([]),
            minimum_occurrences=2,
            correlation_window_seconds=60.0,
            target_risk_level=RiskLevel.CRITICAL,
            target_priority=Priority.CRITICAL,
            reason_template="Test"
        )

def test_minimum_occurrences_must_be_gt_0():
    with pytest.raises(ValidationError):
        RiskEscalationRule(
            source_risk_level=RiskLevel.HIGH,
            source_priority=Priority.HIGH,
            required_event_types=frozenset([EventType.LOITERING]),
            minimum_occurrences=0,
            correlation_window_seconds=60.0,
            target_risk_level=RiskLevel.CRITICAL,
            target_priority=Priority.CRITICAL,
            reason_template="Test"
        )

def test_correlation_window_seconds_must_be_gt_0():
    with pytest.raises(ValidationError):
        RiskEscalationRule(
            source_risk_level=RiskLevel.HIGH,
            source_priority=Priority.HIGH,
            required_event_types=frozenset([EventType.LOITERING]),
            minimum_occurrences=2,
            correlation_window_seconds=0.0,
            target_risk_level=RiskLevel.CRITICAL,
            target_priority=Priority.CRITICAL,
            reason_template="Test"
        )

def test_quiet_period_seconds_must_be_gt_0():
    with pytest.raises(ValidationError):
        RiskDeescalationRule(
            source_risk_level=RiskLevel.HIGH,
            source_priority=Priority.HIGH,
            absence_event_types=frozenset([EventType.LOITERING]),
            quiet_period_seconds=0.0,
            target_risk_level=RiskLevel.MEDIUM,
            target_priority=Priority.MEDIUM,
            reason_template="Test"
        )

def test_empty_reason_template_rejected():
    with pytest.raises(ValidationError):
        RiskEscalationRule(
            source_risk_level=RiskLevel.HIGH,
            source_priority=Priority.HIGH,
            required_event_types=frozenset([EventType.LOITERING]),
            minimum_occurrences=2,
            correlation_window_seconds=60.0,
            target_risk_level=RiskLevel.CRITICAL,
            target_priority=Priority.CRITICAL,
            reason_template=""
        )

def test_default_escalation_policy_constructs_correctly():
    policy = RiskEscalationPolicy.default()
    assert len(policy.rules) == 1
    assert policy.rules[0].target_risk_level == RiskLevel.CRITICAL

def test_default_deescalation_policy_constructs_correctly():
    policy = RiskDeescalationPolicy.default()
    assert len(policy.rules) == 1
    assert policy.rules[0].target_risk_level == RiskLevel.MEDIUM
