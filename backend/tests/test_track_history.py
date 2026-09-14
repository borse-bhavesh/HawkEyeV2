import pytest
from app.services.events.track_history import TrackHistory
from app.services.events.config import EventIntelligenceConfig
from app.services.events.models import TrackObservation
from app.services.tracking.models import BoundingBox

@pytest.fixture
def empty_history():
    config = EventIntelligenceConfig(max_observations_per_track=5)
    return TrackHistory(config)

@pytest.fixture
def sample_observation():
    return TrackObservation(
        track_id=1,
        frame_number=10,
        timestamp_seconds=1.5,
        bounding_box=BoundingBox(x1=10, y1=10, x2=50, y2=50),
        class_id=0,
        class_name="person",
        confidence=0.9
    )

def test_add_and_retrieve_observation(empty_history, sample_observation):
    empty_history.add_observation(sample_observation)
    history = empty_history.get_track_history(1)
    
    assert len(history) == 1
    assert history[0].track_id == 1
    assert history[0].frame_number == 10
    
def test_empty_track_lookup_returns_empty_tuple(empty_history):
    assert empty_history.get_track_history(999) == ()

def test_multiple_observations_chronological(empty_history, sample_observation):
    obs2 = sample_observation.model_copy()
    obs2.frame_number = 11
    obs2.timestamp_seconds = 1.6
    
    empty_history.add_observation(sample_observation)
    empty_history.add_observation(obs2)
    
    history = empty_history.get_track_history(1)
    assert len(history) == 2
    assert history[0].frame_number == 10
    assert history[1].frame_number == 11

def test_reject_out_of_order_observations(empty_history, sample_observation):
    obs2 = sample_observation.model_copy()
    obs2.frame_number = 9 # Out of order
    obs2.timestamp_seconds = 1.4
    
    empty_history.add_observation(sample_observation)
    
    with pytest.raises(ValueError, match="Out-of-order"):
        empty_history.add_observation(obs2)

def test_verify_bounded_history(empty_history, sample_observation):
    # Max size is 5 based on fixture
    for i in range(7):
        obs = sample_observation.model_copy()
        obs.frame_number = 10 + i
        obs.timestamp_seconds = 1.0 + (i * 0.1)
        empty_history.add_observation(obs)
        
    history = empty_history.get_track_history(1)
    assert len(history) == 5
    # The first two (frame 10 and 11) should have been evicted
    assert history[0].frame_number == 12
    assert history[-1].frame_number == 16

def test_verify_track_isolation(empty_history, sample_observation):
    obs2 = sample_observation.model_copy()
    obs2.track_id = 2
    
    empty_history.add_observation(sample_observation)
    empty_history.add_observation(obs2)
    
    history1 = empty_history.get_track_history(1)
    history2 = empty_history.get_track_history(2)
    
    assert len(history1) == 1
    assert len(history2) == 1
    assert history1[0].track_id == 1
    assert history2[0].track_id == 2
    
    active_tracks = empty_history.get_active_track_ids()
    assert set(active_tracks) == {1, 2}

def test_get_recent_observations(empty_history, sample_observation):
    for i in range(4):
        obs = sample_observation.model_copy()
        obs.frame_number = 10 + i
        obs.timestamp_seconds = 1.0 + (i * 0.1)
        empty_history.add_observation(obs)
        
    recent = empty_history.get_recent_observations(1, count=2)
    assert len(recent) == 2
    assert recent[0].frame_number == 12
    assert recent[1].frame_number == 13

def test_returned_history_is_immutable(empty_history, sample_observation):
    empty_history.add_observation(sample_observation)
    history = empty_history.get_track_history(1)
    
    # history is a tuple, caller cannot append/pop
    with pytest.raises(AttributeError):
        history.append(sample_observation)

def test_internal_state_is_copy_protected(empty_history, sample_observation):
    empty_history.add_observation(sample_observation)
    
    # Mutate the caller's reference
    sample_observation.class_id = 999
    
    history = empty_history.get_track_history(1)
    # Stored state should not be mutated
    assert history[0].class_id == 0

def test_remove_track_and_clear(empty_history, sample_observation):
    empty_history.add_observation(sample_observation)
    assert empty_history.get_active_track_ids() == (1,)
    
    empty_history.remove_track(1)
    assert empty_history.get_active_track_ids() == ()
    
    empty_history.add_observation(sample_observation)
    empty_history.clear()
    assert empty_history.get_active_track_ids() == ()

def test_equal_timestamps_follow_policy(empty_history, sample_observation):
    # Depending on tracking setup, two observations in the same frame/timestamp might occur 
    # (e.g. if ID switches back and forth wildly in a single frame processor loop, though unlikely)
    # As per our ValueError logic, equal timestamps/frames are accepted (it's strict less-than that fails)
    obs2 = sample_observation.model_copy()
    
    empty_history.add_observation(sample_observation)
    # Should not raise
    empty_history.add_observation(obs2)
    
    history = empty_history.get_track_history(1)
    assert len(history) == 2
