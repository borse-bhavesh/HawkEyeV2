import pytest
from pydantic import ValidationError
from app.services.events.config import EventIntelligenceConfig

def test_default_event_config():
    config = EventIntelligenceConfig()
    assert config.loitering_duration_seconds == 30.0
    assert config.rapid_movement_speed_threshold == 100.0
    assert config.proximity_distance_threshold == 100.0
    assert config.minimum_event_confidence == 0.5
    assert config.max_observations_per_track == 300
    assert config.track_end_grace_frames == 5

def test_custom_event_config_valid():
    config = EventIntelligenceConfig(
        loitering_duration_seconds=10.0,
        rapid_movement_speed_threshold=100.0,
        proximity_distance_threshold=5.0,
        minimum_event_confidence=0.8,
        max_observations_per_track=100,
        track_end_grace_frames=10
    )
    assert config.loitering_duration_seconds == 10.0
    assert config.rapid_movement_speed_threshold == 100.0
    assert config.proximity_distance_threshold == 5.0
    assert config.minimum_event_confidence == 0.8
    assert config.max_observations_per_track == 100
    assert config.track_end_grace_frames == 10

def test_invalid_loitering_duration_rejected():
    with pytest.raises(ValidationError):
        EventIntelligenceConfig(loitering_duration_seconds=-5.0)

def test_invalid_movement_speed_rejected():
    with pytest.raises(ValidationError):
        EventIntelligenceConfig(rapid_movement_speed_threshold=-1.0)

def test_invalid_proximity_distance_rejected():
    with pytest.raises(ValidationError):
        EventIntelligenceConfig(proximity_distance_threshold=-0.1)

def test_invalid_event_confidence_rejected():
    with pytest.raises(ValidationError):
        EventIntelligenceConfig(minimum_event_confidence=-0.1)
    
    with pytest.raises(ValidationError):
        EventIntelligenceConfig(minimum_event_confidence=1.1)

def test_invalid_max_observations_rejected():
    with pytest.raises(ValidationError):
        EventIntelligenceConfig(max_observations_per_track=0)
    
    with pytest.raises(ValidationError):
        EventIntelligenceConfig(max_observations_per_track=-5)

def test_invalid_track_end_grace_rejected():
    with pytest.raises(ValidationError):
        EventIntelligenceConfig(track_end_grace_frames=-1)

def test_invalid_rapid_movement_rejected():
    with pytest.raises(ValidationError):
        EventIntelligenceConfig(rapid_movement_speed_threshold=0.0)
    with pytest.raises(ValidationError):
        EventIntelligenceConfig(rapid_movement_speed_threshold=-10.0)

def test_invalid_direction_change_rejected():
    with pytest.raises(ValidationError):
        EventIntelligenceConfig(direction_change_angle_threshold=0.0)
    with pytest.raises(ValidationError):
        EventIntelligenceConfig(direction_change_angle_threshold=180.1)

def test_invalid_proximity_rejected():
    with pytest.raises(ValidationError):
        EventIntelligenceConfig(proximity_distance_threshold=0.0)
    with pytest.raises(ValidationError):
        EventIntelligenceConfig(proximity_distance_threshold=-2.0)
