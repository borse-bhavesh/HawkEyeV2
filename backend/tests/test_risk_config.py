import pytest
from pydantic import ValidationError

from app.services.risk.config import RiskConfig

def test_default_risk_config_construction():
    config = RiskConfig()
    assert config.enabled is True

def test_enabled_accepts_boolean():
    config = RiskConfig(enabled=False)
    assert config.enabled is False

def test_invalid_configuration_rejected():
    with pytest.raises(ValidationError):
        RiskConfig(enabled="NOT_A_BOOLEAN")
