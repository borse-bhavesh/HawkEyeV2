import pytest
from pydantic import ValidationError

from app.services.detection.performance_config import DetectionPerformanceConfig

def test_default_configuration():
    config = DetectionPerformanceConfig()
    assert config.device == "auto"
    assert config.image_size == 640
    assert config.half_precision is False
    assert config.max_inference_fps is None

def test_custom_valid_configuration():
    config = DetectionPerformanceConfig(
        device="cuda",
        image_size=1280,
        half_precision=True,
        max_inference_fps=15.0
    )
    assert config.device == "cuda"
    assert config.image_size == 1280
    assert config.half_precision is True
    assert config.max_inference_fps == 15.0

def test_cpu_device_accepted():
    config = DetectionPerformanceConfig(device="cpu")
    assert config.device == "cpu"

def test_cuda_device_accepted():
    config = DetectionPerformanceConfig(device="cuda")
    assert config.device == "cuda"

def test_auto_device_accepted():
    config = DetectionPerformanceConfig(device="auto")
    assert config.device == "auto"

def test_invalid_device_rejected():
    with pytest.raises(ValidationError):
        DetectionPerformanceConfig(device="gpu")

def test_image_size_zero_rejected():
    with pytest.raises(ValidationError):
        DetectionPerformanceConfig(image_size=0)

def test_negative_image_size_rejected():
    with pytest.raises(ValidationError):
        DetectionPerformanceConfig(image_size=-640)

def test_max_inference_fps_none_accepted():
    config = DetectionPerformanceConfig(max_inference_fps=None)
    assert config.max_inference_fps is None

def test_positive_max_inference_fps_accepted():
    config = DetectionPerformanceConfig(max_inference_fps=30.5)
    assert config.max_inference_fps == 30.5

def test_max_inference_fps_zero_rejected():
    with pytest.raises(ValidationError):
        DetectionPerformanceConfig(max_inference_fps=0)

def test_negative_max_inference_fps_rejected():
    with pytest.raises(ValidationError):
        DetectionPerformanceConfig(max_inference_fps=-10.0)

def test_boolean_half_precision_works_correctly():
    config_true = DetectionPerformanceConfig(half_precision=True)
    assert config_true.half_precision is True
    
    config_false = DetectionPerformanceConfig(half_precision=False)
    assert config_false.half_precision is False
