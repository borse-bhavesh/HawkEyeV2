import pytest
from pydantic import ValidationError

from app.services.detection.config import DetectionConfig

def test_valid_configuration():
    config = DetectionConfig(model_name="yolo11n.pt", confidence_threshold=0.5)
    assert config.model_name == "yolo11n.pt"
    assert config.confidence_threshold == 0.5

def test_default_confidence_threshold():
    config = DetectionConfig(model_name="yolo11n.pt")
    assert config.confidence_threshold == 0.25

def test_empty_model_name_rejected():
    with pytest.raises(ValidationError):
        DetectionConfig(model_name="")
    with pytest.raises(ValidationError):
        DetectionConfig(model_name="   ")

def test_confidence_threshold_below_zero_rejected():
    with pytest.raises(ValidationError):
        DetectionConfig(model_name="yolo11n.pt", confidence_threshold=-0.1)

def test_confidence_threshold_above_one_rejected():
    with pytest.raises(ValidationError):
        DetectionConfig(model_name="yolo11n.pt", confidence_threshold=1.1)

def test_boundary_values_accepted():
    config_zero = DetectionConfig(model_name="yolo11n.pt", confidence_threshold=0.0)
    assert config_zero.confidence_threshold == 0.0

    config_one = DetectionConfig(model_name="yolo11n.pt", confidence_threshold=1.0)
    assert config_one.confidence_threshold == 1.0
