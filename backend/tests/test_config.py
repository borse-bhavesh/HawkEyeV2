import pytest
from pydantic import ValidationError
import os
from unittest.mock import patch

from app.core.config import Settings, get_settings, get_detection_config
from app.services.detection.config import DetectionConfig

def test_default_yolo_model_name():
    settings = Settings()
    assert settings.yolo_model_name == "yolo11n.pt"

def test_default_confidence_threshold():
    settings = Settings()
    assert settings.yolo_confidence_threshold == 0.25

def test_valid_custom_model_name():
    settings = Settings(yolo_model_name="yolo11s.pt")
    assert settings.yolo_model_name == "yolo11s.pt"

def test_valid_custom_confidence_threshold():
    settings = Settings(yolo_confidence_threshold=0.50)
    assert settings.yolo_confidence_threshold == 0.50

def test_empty_model_name_rejected():
    with pytest.raises(ValidationError):
        Settings(yolo_model_name="")

def test_whitespace_only_model_name_rejected():
    with pytest.raises(ValidationError):
        Settings(yolo_model_name="   ")

def test_confidence_below_zero_rejected():
    with pytest.raises(ValidationError):
        Settings(yolo_confidence_threshold=-0.1)

def test_confidence_above_one_rejected():
    with pytest.raises(ValidationError):
        Settings(yolo_confidence_threshold=1.1)

def test_boundary_values_accepted():
    settings_zero = Settings(yolo_confidence_threshold=0.0)
    assert settings_zero.yolo_confidence_threshold == 0.0

    settings_one = Settings(yolo_confidence_threshold=1.0)
    assert settings_one.yolo_confidence_threshold == 1.0

def test_environment_variables_can_override_defaults():
    # Use patch.dict to safely mock environment variables for this test
    env_vars = {
        "YOLO_MODEL_NAME": "yolo_env.pt",
        "YOLO_CONFIDENCE_THRESHOLD": "0.75"
    }
    with patch.dict(os.environ, env_vars):
        # We instantiate a fresh Settings object to avoid @lru_cache issues 
        # and test that the Pydantic SettingsConfigDict properly picks up the env vars
        settings = Settings()
        assert settings.yolo_model_name == "yolo_env.pt"
        assert settings.yolo_confidence_threshold == 0.75


# --- STEP 3.7D: Wire Global YOLO Settings into DetectionConfig ---

def test_get_detection_config_returns_detection_config():
    # Verify the returned object is actually a DetectionConfig
    config = get_detection_config()
    assert isinstance(config, DetectionConfig)

def test_get_detection_config_propagates_settings_values():
    # Verify global Settings values are correctly converted into DetectionConfig
    # Ensure it uses the default cached settings from app.core.config
    settings = get_settings()
    config = get_detection_config()
    assert config.model_name == settings.yolo_model_name
    assert config.confidence_threshold == settings.yolo_confidence_threshold

def test_get_detection_config_propagates_custom_settings():
    # Verify custom model name and confidence threshold are propagated
    custom_settings = Settings(
        yolo_model_name="custom_yolo.pt",
        yolo_confidence_threshold=0.88
    )
    # Patch get_settings to return our custom settings
    with patch("app.core.config.get_settings", return_value=custom_settings):
        config = get_detection_config()
        assert config.model_name == "custom_yolo.pt"
        assert config.confidence_threshold == 0.88

def test_get_detection_config_propagates_env_vars():
    # Verify environment-variable values ultimately flow into DetectionConfig
    env_vars = {
        "YOLO_MODEL_NAME": "env_model.pt",
        "YOLO_CONFIDENCE_THRESHOLD": "0.42"
    }
    with patch.dict(os.environ, env_vars):
        # We need to create a fresh Settings instance inside the context manager
        # and patch get_settings to return it to avoid lru_cache issues
        fresh_settings = Settings()
        with patch("app.core.config.get_settings", return_value=fresh_settings):
            config = get_detection_config()
            assert config.model_name == "env_model.pt"
            assert config.confidence_threshold == 0.42

def test_get_detection_config_validation_remains_active():
    # Verify DetectionConfig validation remains active even when populated from factory
    invalid_settings = Settings()
    # Force bypass Pydantic validation on the Settings object to test DetectionConfig's validation
    object.__setattr__(invalid_settings, 'yolo_model_name', '') 
    
    with patch("app.core.config.get_settings", return_value=invalid_settings):
        with pytest.raises(ValidationError):
            get_detection_config()
