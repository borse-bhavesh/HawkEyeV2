import pytest
from pydantic import ValidationError
from app.services.tracking.config import TrackingConfig

# 1. TrackingConfig default construction works.
def test_tracking_config_defaults():
    config = TrackingConfig()
    assert config.tracker_type == "bytetrack"
    assert config.track_high_thresh == 0.5
    assert config.track_low_thresh == 0.1
    assert config.new_track_thresh == 0.6
    assert config.track_buffer == 30
    assert config.match_thresh == 0.8
    assert config.fuse_score is True

# 2. Valid threshold values are accepted.
def test_tracking_config_valid_thresholds():
    config = TrackingConfig(
        track_high_thresh=0.0,
        track_low_thresh=1.0,
        new_track_thresh=0.5,
        match_thresh=0.9
    )
    assert config.track_high_thresh == 0.0
    assert config.track_low_thresh == 1.0
    assert config.new_track_thresh == 0.5
    assert config.match_thresh == 0.9

# 3. Invalid threshold values are rejected.
def test_tracking_config_negative_thresholds_rejected():
    with pytest.raises(ValidationError):
        TrackingConfig(track_high_thresh=-0.1)
    with pytest.raises(ValidationError):
        TrackingConfig(track_low_thresh=-0.5)
    with pytest.raises(ValidationError):
        TrackingConfig(new_track_thresh=-0.01)
    with pytest.raises(ValidationError):
        TrackingConfig(match_thresh=-1.0)

def test_tracking_config_thresholds_above_one_rejected():
    with pytest.raises(ValidationError):
        TrackingConfig(track_high_thresh=1.1)
    with pytest.raises(ValidationError):
        TrackingConfig(track_low_thresh=1.5)
    with pytest.raises(ValidationError):
        TrackingConfig(new_track_thresh=2.0)
    with pytest.raises(ValidationError):
        TrackingConfig(match_thresh=1.001)

# 4. Invalid tracker_type is rejected.
def test_tracking_config_invalid_tracker_type_rejected():
    with pytest.raises(ValidationError):
        TrackingConfig(tracker_type="deep_sort")
        
    with pytest.raises(ValidationError):
        TrackingConfig(tracker_type="BYTEtrack")  # literal match is exact

# 5. Invalid track_buffer is rejected.
def test_tracking_config_invalid_track_buffer_rejected():
    with pytest.raises(ValidationError):
        TrackingConfig(track_buffer=0)  # ge=1
        
    with pytest.raises(ValidationError):
        TrackingConfig(track_buffer=-10)
