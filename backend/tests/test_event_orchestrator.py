from typing import List
from app.services.events.config import EventIntelligenceConfig
from app.services.events.orchestrator import EventOrchestrator
from app.services.tracking.models import TrackedObject, BoundingBox
from app.services.events.models import EventType

def test_event_orchestrator_initialization():
    config = EventIntelligenceConfig()
    orchestrator = EventOrchestrator(config=config)
    
    assert orchestrator.lifecycle_engine is not None
    assert orchestrator.zone_engine is not None
    assert orchestrator.loitering_engine is not None
    assert orchestrator.rapid_movement_engine is not None
    assert orchestrator.direction_change_engine is not None
    assert orchestrator.proximity_engine is not None
    
    # Check deterministic order
    assert orchestrator.engines[0] == orchestrator.lifecycle_engine
    assert orchestrator.engines[1] == orchestrator.zone_engine
    assert orchestrator.engines[2] == orchestrator.loitering_engine
    assert orchestrator.engines[3] == orchestrator.rapid_movement_engine
    assert orchestrator.engines[4] == orchestrator.direction_change_engine
    assert orchestrator.engines[5] == orchestrator.proximity_engine

def test_event_orchestrator_lifecycle_and_cleanup():
    """
    Tests that EventOrchestrator propagates TRACK_ENDED to remove_track.
    """
    config = EventIntelligenceConfig(track_end_grace_frames=1)
    orchestrator = EventOrchestrator(config=config)
    
    bbox = BoundingBox(x1=0.0, y1=0.0, x2=10.0, y2=10.0)
    obj = TrackedObject(track_id=1, bounding_box=bbox, class_id=0, class_name="person", confidence=0.9)
    
    # Frame 1: Object appears
    events1 = orchestrator.process_frame(1, 1.0, [obj])
    assert any(e.event_type == EventType.TRACK_STARTED for e in events1)
    
    # Frame 2: Object missing (within grace)
    events2 = orchestrator.process_frame(2, 2.0, [])
    assert not any(e.event_type == EventType.TRACK_ENDED for e in events2)
    
    # Frame 3: Object missing (grace exceeded), TRACK_ENDED emitted
    events3 = orchestrator.process_frame(3, 3.0, [])
    assert any(e.event_type == EventType.TRACK_ENDED for e in events3)
    
    # Because TRACK_ENDED was emitted, orchestrator should have called remove_track
    # on downstream engines. We can verify rapid_movement_engine internal state is clean.
    assert 1 not in orchestrator.rapid_movement_engine._state
    assert 1 not in orchestrator.direction_change_engine._state
    assert 1 not in orchestrator.proximity_engine._state

def test_event_orchestrator_finalize():
    """
    Tests that finalize() correctly concludes tracks using their real timestamps.
    """
    config = EventIntelligenceConfig(track_end_grace_frames=5)
    orchestrator = EventOrchestrator(config=config)
    
    bbox = BoundingBox(x1=0.0, y1=0.0, x2=10.0, y2=10.0)
    obj = TrackedObject(track_id=42, bounding_box=bbox, class_id=0, class_name="person", confidence=0.9)
    
    orchestrator.process_frame(10, 10.5, [obj])
    
    # Finalize without reaching grace period
    final_events = orchestrator.finalize()
    
    track_ended_events = [e for e in final_events if e.event_type == EventType.TRACK_ENDED]
    assert len(track_ended_events) == 1
    
    event = track_ended_events[0]
    assert event.track_id == 42
    assert event.frame_number == 10
    assert event.timestamp_seconds == 10.5
    assert event.evidence["end_of_stream"] is True
