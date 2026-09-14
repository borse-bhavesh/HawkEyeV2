import pytest
from app.services.events.config import EventIntelligenceConfig
from app.services.events.models import EventType
from app.services.events.rapid_movement_engine import RapidMovementEngine
from app.services.tracking.models import TrackedObject, BoundingBox

@pytest.fixture
def config():
    return EventIntelligenceConfig(rapid_movement_speed_threshold=100.0)

@pytest.fixture
def engine(config):
    return RapidMovementEngine(config)

def create_obj(track_id: int, center_x: float, bottom_y: float) -> TrackedObject:
    # We use center_x and bottom_y as x1 and y1. 
    # Reference point will be x_ref = center_x + 1.0, y_ref = bottom_y + 2.0
    return TrackedObject(
        track_id=track_id,
        bounding_box=BoundingBox(x1=center_x, y1=bottom_y, x2=center_x+2, y2=bottom_y+2),
        class_id=0, class_name="person", confidence=0.9
    )

def test_first_observation_produces_no_event(engine):
    events = engine.process(1, 0.0, [create_obj(1, 0, 0)])
    assert len(events) == 0

def test_stationary_object_produces_no_event(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)])
    events = engine.process(2, 1.0, [create_obj(1, 0, 0)])
    assert len(events) == 0

def test_slow_movement_below_threshold_produces_no_event(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)])
    # dx=80, dt=1.0 => speed=80 < 100
    events = engine.process(2, 1.0, [create_obj(1, 80, 0)])
    assert len(events) == 0

def test_speed_exactly_equal_to_threshold_produces_one_event(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)])
    # dx=100, dt=1.0 => speed=100
    events = engine.process(2, 1.0, [create_obj(1, 100, 0)])
    assert len(events) == 1
    assert events[0].event_type == EventType.RAPID_MOVEMENT

def test_speed_above_threshold_produces_one_event(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)])
    # dy=150, dt=1.0 => speed=150
    events = engine.process(2, 1.0, [create_obj(1, 0, 150)])
    assert len(events) == 1
    assert events[0].event_type == EventType.RAPID_MOVEMENT

def test_continued_rapid_movement_does_not_produce_duplicate_events(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)])
    engine.process(2, 1.0, [create_obj(1, 100, 0)]) # Emits
    events = engine.process(3, 2.0, [create_obj(1, 200, 0)]) # Speed=100, already active
    assert len(events) == 0

def test_rapid_to_slow_resets_rapid_state(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)])
    engine.process(2, 1.0, [create_obj(1, 150, 0)]) # Emits
    
    # Move slowly: dx=10, dt=1.0 => speed=10
    events_slow = engine.process(3, 2.0, [create_obj(1, 160, 0)])
    assert len(events_slow) == 0
    # State is now inactive

def test_slow_to_rapid_after_reset_generates_new_event(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)])
    engine.process(2, 1.0, [create_obj(1, 150, 0)]) # RAPID -> Emits
    engine.process(3, 2.0, [create_obj(1, 160, 0)]) # SLOW -> Resets state
    
    # RAPID again: dx=150, dt=1.0
    events_rapid = engine.process(4, 3.0, [create_obj(1, 310, 0)])
    assert len(events_rapid) == 1
    assert events_rapid[0].event_type == EventType.RAPID_MOVEMENT

def test_multiple_tracks_are_independent(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0), create_obj(2, 0, 0)])
    
    # Track 1 rapid (dx=150), Track 2 slow (dx=10)
    events = engine.process(2, 1.0, [create_obj(1, 150, 0), create_obj(2, 10, 0)])
    assert len(events) == 1
    assert events[0].track_id == 1

def test_temporary_track_disappearance_does_not_automatically_reset_state(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)])
    engine.process(2, 1.0, [create_obj(1, 150, 0)]) # RAPID -> Emits
    
    # Disappears
    engine.process(3, 2.0, [])
    
    # Reappears and continues rapid movement (distance=150 since t=1, delta_t=2.0 -> speed=75)
    # Wait, distance is 150 (from 150 to 300) over 2.0 seconds (from 1.0 to 3.0). Speed = 75 (SLOW)
    # If it was speed = 150: distance=300, delta_t=2.0 -> speed=150
    events = engine.process(4, 3.0, [create_obj(1, 450, 0)]) # RAPID
    assert len(events) == 0 # Was already active and didn't reset

def test_reappearing_track_uses_previous_valid_observation(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)]) # SLOW (first obs)
    
    engine.process(2, 1.0, []) # Disappears
    
    # Reappears at t=3.0. Previous point (0,0) at t=0.0. delta_t=3.0
    # To be rapid, needs distance=300
    events = engine.process(3, 3.0, [create_obj(1, 300, 0)]) # Speed=100 -> Emits
    assert len(events) == 1

def test_timestamp_based_speed_calculation(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)])
    # dx=10, dt=0.05 => speed=200 > 100
    events = engine.process(2, 0.05, [create_obj(1, 10, 0)])
    assert len(events) == 1

def test_frame_number_differences_are_not_used(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)])
    # Frame jump by 100, but time jump only 0.1s. dx=15, speed=150
    events = engine.process(100, 0.1, [create_obj(1, 15, 0)])
    assert len(events) == 1

def test_equal_timestamps_do_not_cause_division_by_zero(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)])
    events = engine.process(2, 0.0, [create_obj(1, 10, 0)])
    assert len(events) == 0 # Should ignore or just update point
    
    # Ensure point updated: next obs at t=1.0, x=110 => dx=100 from updated point (10), speed=100 -> Emits
    events2 = engine.process(3, 1.0, [create_obj(1, 110, 0)])
    assert len(events2) == 1

def test_backward_timestamps_are_safely_handled(engine):
    engine.process(1, 1.0, [create_obj(1, 0, 0)])
    events = engine.process(2, 0.0, [create_obj(1, 100, 0)]) # Ignored
    assert len(events) == 0
    
    # Next obs t=2.0. Base is still t=1.0. dx=100, dt=1.0 => Emits
    events2 = engine.process(3, 2.0, [create_obj(1, 100, 0)])
    assert len(events2) == 1

def test_event_type_is_rapid_movement(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)])
    events = engine.process(2, 1.0, [create_obj(1, 150, 0)])
    assert events[0].event_type == EventType.RAPID_MOVEMENT

def test_event_frame_corresponds_to_triggering_observation(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)])
    engine.process(2, 1.0, [create_obj(1, 10, 0)])
    events = engine.process(3, 2.0, [create_obj(1, 150, 0)])
    assert events[0].frame_number == 3

def test_event_timestamp_corresponds_to_triggering_observation(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)])
    events = engine.process(2, 1.5, [create_obj(1, 200, 0)])
    assert events[0].timestamp_seconds == 1.5

def test_evidence_contains_reference_points(engine):
    engine.process(1, 0.0, [create_obj(1, 10, 20)])
    events = engine.process(2, 1.0, [create_obj(1, 110, 20)])
    # reference points are shifted by +1.0 in X and +2.0 in Y due to BoundingBox creation
    assert events[0].evidence["previous_reference_point"] == {"x": 11.0, "y": 22.0}
    assert events[0].evidence["current_reference_point"] == {"x": 111.0, "y": 22.0}

def test_evidence_contains_calculated_distance(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)])
    events = engine.process(2, 1.0, [create_obj(1, 150, 0)])
    assert events[0].evidence["distance_pixels"] == 150.0

def test_evidence_contains_elapsed_time(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)])
    events = engine.process(2, 1.5, [create_obj(1, 150, 0)])
    assert events[0].evidence["elapsed_seconds"] == 1.5

def test_evidence_contains_observed_speed(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)])
    events = engine.process(2, 1.5, [create_obj(1, 150, 0)])
    assert events[0].evidence["observed_speed_pixels_per_second"] == 100.0

def test_evidence_contains_configured_threshold(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)])
    events = engine.process(2, 1.0, [create_obj(1, 150, 0)])
    assert events[0].evidence["configured_threshold_pixels_per_second"] == 100.0

def test_reset_clears_all_state(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)])
    engine.reset()
    # At t=1.0, state is cleared, so it acts as first observation
    events = engine.process(2, 1.0, [create_obj(1, 150, 0)])
    assert len(events) == 0

def test_remove_track_only_removes_selected_track(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0), create_obj(2, 0, 0)])
    engine.remove_track(1)
    
    events = engine.process(2, 1.0, [create_obj(1, 150, 0), create_obj(2, 150, 0)])
    assert len(events) == 1
    assert events[0].track_id == 2 # Track 1 was removed, so this is its first obs

def test_multiple_rapid_tracks_generate_deterministic_ordering(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0), create_obj(2, 0, 0)])
    events = engine.process(2, 1.0, [create_obj(2, 150, 0), create_obj(1, 150, 0)])
    assert len(events) == 2
    assert events[0].track_id == 1
    assert events[1].track_id == 2

def test_event_ids_are_unique(engine):
    engine.process(1, 0.0, [create_obj(1, 0, 0)])
    e1 = engine.process(2, 1.0, [create_obj(1, 150, 0)])
    engine.process(3, 2.0, [create_obj(1, 160, 0)]) # Slow down
    e2 = engine.process(4, 3.0, [create_obj(1, 310, 0)]) # Rapid again
    assert e1[0].event_id != e2[0].event_id
