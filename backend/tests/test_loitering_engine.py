import pytest
from app.services.events.config import EventIntelligenceConfig
from app.services.events.models import EventType
from app.services.events.zones import Zone, Point2D
from app.services.events.loitering_engine import LoiteringEngine
from app.services.tracking.models import TrackedObject, BoundingBox

@pytest.fixture
def config():
    return EventIntelligenceConfig(loitering_duration_seconds=10.0)

@pytest.fixture
def zone_a():
    return Zone(
        zone_id="zoneA", name="Zone A",
        polygon=[Point2D(x=0, y=0), Point2D(x=10, y=0), Point2D(x=10, y=10), Point2D(x=0, y=10)]
    )

@pytest.fixture
def zone_b():
    return Zone(
        zone_id="zoneB", name="Zone B",
        polygon=[Point2D(x=20, y=0), Point2D(x=30, y=0), Point2D(x=30, y=10), Point2D(x=20, y=10)]
    )

@pytest.fixture
def engine(config, zone_a):
    return LoiteringEngine(config, [zone_a])

@pytest.fixture
def multi_engine(config, zone_a, zone_b):
    return LoiteringEngine(config, [zone_a, zone_b])

def create_obj(track_id: int, center_x: float, bottom_y: float) -> TrackedObject:
    return TrackedObject(
        track_id=track_id,
        bounding_box=BoundingBox(x1=center_x-2, y1=bottom_y-4, x2=center_x+2, y2=bottom_y),
        class_id=0, class_name="person", confidence=0.9
    )

def test_first_observation_outside_no_event(engine):
    events = engine.process(1, 0.0, [create_obj(1, 15, 15)]) # OUTSIDE
    assert len(events) == 0

def test_first_observation_inside_no_loitering_event(engine):
    events = engine.process(1, 0.0, [create_obj(1, 5, 5)]) # INSIDE
    assert len(events) == 0

def test_inside_duration_below_threshold_no_event(engine):
    engine.process(1, 0.0, [create_obj(1, 5, 5)]) # INSIDE
    events = engine.process(2, 9.9, [create_obj(1, 5, 5)]) # INSIDE, duration=9.9
    assert len(events) == 0

def test_duration_exactly_equal_threshold_one_event(engine):
    engine.process(1, 0.0, [create_obj(1, 5, 5)])
    events = engine.process(2, 10.0, [create_obj(1, 5, 5)]) # duration=10.0
    assert len(events) == 1
    assert events[0].event_type == EventType.LOITERING

def test_duration_above_threshold_one_event(engine):
    engine.process(1, 0.0, [create_obj(1, 5, 5)])
    events = engine.process(2, 12.0, [create_obj(1, 5, 5)]) # duration=12.0
    assert len(events) == 1
    assert events[0].event_type == EventType.LOITERING

def test_continued_presence_after_event_no_duplicate(engine):
    engine.process(1, 0.0, [create_obj(1, 5, 5)])
    engine.process(2, 10.0, [create_obj(1, 5, 5)]) # Emits event
    events = engine.process(3, 15.0, [create_obj(1, 5, 5)]) # Still inside, no new event
    assert len(events) == 0

def test_leaving_zone_resets_continuous_presence(engine):
    engine.process(1, 0.0, [create_obj(1, 5, 5)]) # Start at t=0
    engine.process(2, 5.0, [create_obj(1, 15, 15)]) # OUTSIDE at t=5
    events = engine.process(3, 11.0, [create_obj(1, 5, 5)]) # Re-enters at t=11
    # Duration relative to original t=0 is 11.0, but timer reset at t=5.
    # New timer started at t=11. Duration is 0.
    assert len(events) == 0

def test_reentering_zone_starts_new_timer(engine):
    engine.process(1, 0.0, [create_obj(1, 5, 5)]) # Starts at t=0
    engine.process(2, 5.0, [create_obj(1, 15, 15)]) # OUTSIDE, timer resets
    engine.process(3, 10.0, [create_obj(1, 5, 5)]) # Re-enters, new timer starts at t=10
    events = engine.process(4, 15.0, [create_obj(1, 5, 5)]) # New duration = 5.0, no event yet
    assert len(events) == 0

def test_reentry_can_generate_new_loitering_event(engine):
    engine.process(1, 0.0, [create_obj(1, 5, 5)]) 
    e1 = engine.process(2, 10.0, [create_obj(1, 5, 5)]) # Emits LOITERING
    engine.process(3, 12.0, [create_obj(1, 15, 15)]) # Leaves
    engine.process(4, 20.0, [create_obj(1, 5, 5)]) # Re-enters
    e2 = engine.process(5, 30.0, [create_obj(1, 5, 5)]) # Emits new LOITERING (duration=10)
    
    assert len(e1) == 1
    assert len(e2) == 1
    assert e1[0].event_id != e2[0].event_id

def test_multiple_tracks_are_independent(engine):
    engine.process(1, 0.0, [create_obj(1, 5, 5)]) # Track 1 in
    engine.process(2, 5.0, [create_obj(1, 5, 5), create_obj(2, 5, 5)]) # Track 2 in
    
    # At t=10, Track 1 duration=10, Track 2 duration=5
    events = engine.process(3, 10.0, [create_obj(1, 5, 5), create_obj(2, 5, 5)])
    assert len(events) == 1
    assert events[0].track_id == 1

def test_multiple_zones_are_independent(multi_engine):
    multi_engine.process(1, 0.0, [create_obj(1, 5, 5)]) # Track 1 in Zone A
    multi_engine.process(2, 5.0, [create_obj(1, 25, 5)]) # Track 1 leaves A, enters B
    
    # At t=10, duration in A was reset. Duration in B is 5.
    events = multi_engine.process(3, 10.0, [create_obj(1, 25, 5)])
    assert len(events) == 0
    
    # At t=15, duration in B is 10
    events_b = multi_engine.process(4, 15.0, [create_obj(1, 25, 5)])
    assert len(events_b) == 1
    assert events_b[0].evidence["zone_id"] == "zoneB"

def test_temporary_track_disappearance_does_not_reset_timer(engine):
    engine.process(1, 0.0, [create_obj(1, 5, 5)])
    engine.process(2, 5.0, []) # Disappears
    events = engine.process(3, 10.0, [create_obj(1, 5, 5)]) # Reappears. Timer still intact.
    assert len(events) == 1
    assert events[0].event_type == EventType.LOITERING

def test_explicit_outside_observation_resets_timer(engine):
    engine.process(1, 0.0, [create_obj(1, 5, 5)])
    engine.process(2, 5.0, [create_obj(1, 15, 15)]) # Explicitly outside
    events = engine.process(3, 10.0, [create_obj(1, 5, 5)]) # Inside again
    # Total duration since t=0 is 10, but timer was reset at t=5.
    assert len(events) == 0

def test_timestamp_based_duration_used_rather_than_frame_count(engine):
    engine.process(1, 0.0, [create_obj(1, 5, 5)])
    # Large timestamp jump on next frame
    events = engine.process(2, 10.0, [create_obj(1, 5, 5)])
    assert len(events) == 1

def test_event_frame_number_corresponds_to_first_observation_satisfying_threshold(engine):
    engine.process(1, 0.0, [create_obj(1, 5, 5)])
    engine.process(2, 8.0, [create_obj(1, 5, 5)])
    events = engine.process(3, 11.0, [create_obj(1, 5, 5)])
    assert events[0].frame_number == 3

def test_event_timestamp_corresponds_to_triggering_observation(engine):
    engine.process(1, 0.0, [create_obj(1, 5, 5)])
    events = engine.process(2, 10.5, [create_obj(1, 5, 5)])
    assert events[0].timestamp_seconds == 10.5

def test_evidence_contains_configured_threshold_and_observed_duration(engine):
    engine.process(1, 0.0, [create_obj(1, 5, 5)])
    events = engine.process(2, 12.5, [create_obj(1, 5, 5)])
    assert events[0].evidence["configured_threshold_seconds"] == 10.0
    assert events[0].evidence["observed_duration_seconds"] == 12.5

def test_event_contains_loitering_type(engine):
    engine.process(1, 0.0, [create_obj(1, 5, 5)])
    events = engine.process(2, 10.0, [create_obj(1, 5, 5)])
    assert events[0].event_type == EventType.LOITERING

def test_reset_clears_all_state(engine):
    engine.process(1, 0.0, [create_obj(1, 5, 5)])
    engine.reset()
    # At t=10, the duration relative to t=0 is 10, but state was cleared.
    # Engine will treat this as first observation inside.
    events = engine.process(2, 10.0, [create_obj(1, 5, 5)])
    assert len(events) == 0

def test_remove_track_only_removes_that_tracks_state(engine):
    engine.process(1, 0.0, [create_obj(1, 5, 5), create_obj(2, 5, 5)])
    engine.remove_track(1)
    
    events = engine.process(2, 10.0, [create_obj(1, 5, 5), create_obj(2, 5, 5)])
    assert len(events) == 1
    assert events[0].track_id == 2 # Track 1's timer was removed, so it didn't trigger

def test_deterministic_event_ordering(multi_engine):
    multi_engine.process(1, 0.0, [create_obj(1, 5, 5), create_obj(2, 25, 5)])
    
    # Both hit threshold
    events = multi_engine.process(2, 10.0, [create_obj(2, 25, 5), create_obj(1, 5, 5)]) # Reverse order in list
    assert len(events) == 2
    
    # Should be sorted by track_id
    assert events[0].track_id == 1
    assert events[0].evidence["zone_id"] == "zoneA"
    
    assert events[1].track_id == 2
    assert events[1].evidence["zone_id"] == "zoneB"

def test_event_emitted_only_once_per_continuous_presence(engine):
    engine.process(1, 0.0, [create_obj(1, 5, 5)])
    e1 = engine.process(2, 10.0, [create_obj(1, 5, 5)])
    e2 = engine.process(3, 11.0, [create_obj(1, 5, 5)])
    e3 = engine.process(4, 12.0, [create_obj(1, 5, 5)])
    
    assert len(e1) == 1
    assert len(e2) == 0
    assert len(e3) == 0
