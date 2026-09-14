import pytest
from app.services.events.config import EventIntelligenceConfig
from app.services.events.lifecycle_engine import LifecycleEngine
from app.services.events.models import EventType
from app.services.tracking.models import TrackedObject, BoundingBox

@pytest.fixture
def config():
    return EventIntelligenceConfig(track_end_grace_frames=2)

@pytest.fixture
def engine(config):
    return LifecycleEngine(config)

def create_obj(track_id: int) -> TrackedObject:
    return TrackedObject(
        track_id=track_id,
        bounding_box=BoundingBox(x1=0, y1=0, x2=10, y2=10),
        class_id=0,
        class_name="person",
        confidence=0.9
    )

def test_first_observation_creates_track_started(engine):
    events = engine.process(frame_number=1, timestamp_seconds=0.1, tracked_objects=[create_obj(1)])
    
    assert len(events) == 1
    assert events[0].event_type == EventType.TRACK_STARTED
    assert events[0].track_id == 1
    assert events[0].evidence["lifecycle_state"] == "STARTED"
    assert events[0].evidence["first_observation_frame"] == 1

def test_repeated_observation_does_not_emit_started(engine):
    engine.process(frame_number=1, timestamp_seconds=0.1, tracked_objects=[create_obj(1)])
    events = engine.process(frame_number=2, timestamp_seconds=0.2, tracked_objects=[create_obj(1)])
    
    assert len(events) == 0

def test_multiple_tracks_generate_own_events(engine):
    events = engine.process(frame_number=1, timestamp_seconds=0.1, tracked_objects=[create_obj(1), create_obj(2)])
    
    assert len(events) == 2
    assert events[0].event_type == EventType.TRACK_STARTED
    assert events[0].track_id == 1
    assert events[1].event_type == EventType.TRACK_STARTED
    assert events[1].track_id == 2

def test_missing_track_grace_period_active(engine):
    engine.process(frame_number=1, timestamp_seconds=0.1, tracked_objects=[create_obj(1)])
    
    # Missing frame 2 (1 absent) - grace is 2
    events = engine.process(frame_number=2, timestamp_seconds=0.2, tracked_objects=[])
    assert len(events) == 0
    
    # Missing frame 3 (2 absent) - grace is 2
    events = engine.process(frame_number=3, timestamp_seconds=0.3, tracked_objects=[])
    assert len(events) == 0

def test_track_reappearing_within_grace(engine):
    engine.process(frame_number=1, timestamp_seconds=0.1, tracked_objects=[create_obj(1)])
    
    # Missing frame 2 (1 absent)
    engine.process(frame_number=2, timestamp_seconds=0.2, tracked_objects=[])
    
    # Reappears frame 3
    events = engine.process(frame_number=3, timestamp_seconds=0.3, tracked_objects=[create_obj(1)])
    assert len(events) == 0

def test_missing_track_exceeds_grace_emits_ended(engine):
    engine.process(frame_number=1, timestamp_seconds=0.1, tracked_objects=[create_obj(1)])
    
    # Missing frame 2 (1 absent)
    engine.process(frame_number=2, timestamp_seconds=0.2, tracked_objects=[])
    # Missing frame 3 (2 absent)
    engine.process(frame_number=3, timestamp_seconds=0.3, tracked_objects=[])
    
    # Missing frame 4 (3 absent) -> exceeds grace of 2
    events = engine.process(frame_number=4, timestamp_seconds=0.4, tracked_objects=[])
    
    assert len(events) == 1
    assert events[0].event_type == EventType.TRACK_ENDED
    assert events[0].track_id == 1
    assert events[0].evidence["lifecycle_state"] == "ENDED"
    assert events[0].evidence["last_observed_frame"] == 1
    assert events[0].evidence["consecutive_absence_count"] == 3

def test_ended_track_emits_only_once(engine):
    engine.process(frame_number=1, timestamp_seconds=0.1, tracked_objects=[create_obj(1)])
    engine.process(frame_number=2, timestamp_seconds=0.2, tracked_objects=[])
    engine.process(frame_number=3, timestamp_seconds=0.3, tracked_objects=[])
    
    # Emits ended
    events1 = engine.process(frame_number=4, timestamp_seconds=0.4, tracked_objects=[])
    assert len(events1) == 1
    
    # Should not emit ended again
    events2 = engine.process(frame_number=5, timestamp_seconds=0.5, tracked_objects=[])
    assert len(events2) == 0

def test_later_observation_after_ended_generates_new_started(engine):
    engine.process(frame_number=1, timestamp_seconds=0.1, tracked_objects=[create_obj(1)])
    engine.process(frame_number=2, timestamp_seconds=0.2, tracked_objects=[])
    engine.process(frame_number=3, timestamp_seconds=0.3, tracked_objects=[])
    engine.process(frame_number=4, timestamp_seconds=0.4, tracked_objects=[]) # Ends
    
    # Reappears
    events = engine.process(frame_number=5, timestamp_seconds=0.5, tracked_objects=[create_obj(1)])
    
    assert len(events) == 1
    assert events[0].event_type == EventType.TRACK_STARTED
    assert events[0].track_id == 1
    assert events[0].evidence["first_observation_frame"] == 5

def test_reset_clears_state(engine):
    engine.process(frame_number=1, timestamp_seconds=0.1, tracked_objects=[create_obj(1)])
    
    engine.reset()
    
    # The same track appearing again is considered a new start
    events = engine.process(frame_number=2, timestamp_seconds=0.2, tracked_objects=[create_obj(1)])
    assert len(events) == 1
    assert events[0].event_type == EventType.TRACK_STARTED
    assert events[0].track_id == 1

def test_multiple_tracks_end_independently(engine):
    engine.process(frame_number=1, timestamp_seconds=0.1, tracked_objects=[create_obj(1), create_obj(2)])
    engine.process(frame_number=2, timestamp_seconds=0.2, tracked_objects=[create_obj(2)])
    engine.process(frame_number=3, timestamp_seconds=0.3, tracked_objects=[create_obj(2)])
    
    # Track 1 ends
    events = engine.process(frame_number=4, timestamp_seconds=0.4, tracked_objects=[create_obj(2)])
    assert len(events) == 1
    assert events[0].event_type == EventType.TRACK_ENDED
    assert events[0].track_id == 1
    
    # Track 2 ends later
    engine.process(frame_number=5, timestamp_seconds=0.5, tracked_objects=[])
    engine.process(frame_number=6, timestamp_seconds=0.6, tracked_objects=[])
    events2 = engine.process(frame_number=7, timestamp_seconds=0.7, tracked_objects=[])
    assert len(events2) == 1
    assert events2[0].event_type == EventType.TRACK_ENDED
    assert events2[0].track_id == 2
