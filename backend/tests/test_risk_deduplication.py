import pytest
from pydantic import ValidationError

from app.services.risk.deduplication import RiskDeduplicationPolicy

def test_default_policy_constructs_successfully():
    policy = RiskDeduplicationPolicy()
    assert policy is not None

def test_default_enabled_is_true():
    policy = RiskDeduplicationPolicy()
    assert policy.enabled is True

def test_default_includes_risk_level():
    policy = RiskDeduplicationPolicy()
    assert policy.include_risk_level is True

def test_default_includes_priority():
    policy = RiskDeduplicationPolicy()
    assert policy.include_priority is True

def test_invalid_policy_values_are_rejected():
    with pytest.raises(ValidationError):
        RiskDeduplicationPolicy(enabled="NotABool")
    
    with pytest.raises(ValidationError):
        RiskDeduplicationPolicy(include_risk_level="NotABool")

    with pytest.raises(ValidationError):
        RiskDeduplicationPolicy(include_priority="NotABool")
