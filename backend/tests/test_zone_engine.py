import pytest
from app.services.events.models import EventType
from app.services.events.zones import Zone, Point2D
from app.services.events.zone_engine import ZoneEngine
from app.services.tracking.models import TrackedObject, BoundingBox

@pytest.fixture
def square_zone():
    # 10x10 square at origin
    return Zone(
        zone_id="zoneA",
        name="Zone A",
        polygon=[Point2D(x=0, y=0), Point2D(x=10, y=0), Point2D(x=10, y=10), Point2D(x=0, y=10)]
    )

@pytest.fixture
def second_zone():
    # 10x10 square shifted to x=20
    return Zone(
        zone_id="zoneB",
        name="Zone B",
        polygon=[Point2D(x=20, y=0), Point2D(x=30, y=0), Point2D(x=30, y=10), Point2D(x=20, y=10)]
    )

@pytest.fixture
def engine(square_zone):
    return ZoneEngine([square_zone])

@pytest.fixture
def multi_engine(square_zone, second_zone):
    return ZoneEngine([square_zone, second_zone])

def create_obj(track_id: int, center_x: float, bottom_y: float) -> TrackedObject:
    # Reverse engineer a bounding box that has the target reference point (center_x, bottom_y)
    # x_center = (x1 + x2)/2
    # bottom_y = y2
    width = 4
    x1 = center_x - 2
    x2 = center_x + 2
    y2 = bottom_y
    y1 = bottom_y - 4
    return TrackedObject(
        track_id=track_id,
        bounding_box=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
        class_id=0, class_name="person", confidence=0.9
    )

def test_first_observation_outside_no_event(engine):
    # Reference point at (15, 15) -> OUTSIDE
    events = engine.process(1, 0.1, [create_obj(1, 15, 15)])
    assert len(events) == 0

def test_first_observation_inside_no_event(engine):
    # Reference point at (5, 5) -> INSIDE
    events = engine.process(1, 0.1, [create_obj(1, 5, 5)])
    assert len(events) == 0

def test_outside_to_outside_no_event(engine):
    engine.process(1, 0.1, [create_obj(1, 15, 15)]) # OUTSIDE
    events = engine.process(2, 0.2, [create_obj(1, 16, 16)]) # OUTSIDE
    assert len(events) == 0

def test_inside_to_inside_no_event(engine):
    engine.process(1, 0.1, [create_obj(1, 5, 5)]) # INSIDE
    events = engine.process(2, 0.2, [create_obj(1, 6, 6)]) # INSIDE
    assert len(events) == 0

def test_outside_to_inside_emits_entry(engine):
    engine.process(1, 0.1, [create_obj(1, 15, 15)]) # OUTSIDE
    events = engine.process(2, 0.2, [create_obj(1, 5, 5)]) # INSIDE
    
    assert len(events) == 1
    assert events[0].event_type == EventType.ZONE_ENTRY
    assert events[0].track_id == 1
    assert events[0].frame_number == 2
    assert events[0].evidence["zone_id"] == "zoneA"
    assert events[0].evidence["previous_membership"] == "OUTSIDE"
    assert events[0].evidence["current_membership"] == "INSIDE"
    assert events[0].evidence["transition_type"] == "ENTRY"

def test_inside_to_outside_emits_exit(engine):
    engine.process(1, 0.1, [create_obj(1, 5, 5)]) # INSIDE
    events = engine.process(2, 0.2, [create_obj(1, 15, 15)]) # OUTSIDE
    
    assert len(events) == 1
    assert events[0].event_type == EventType.ZONE_EXIT
    assert events[0].track_id == 1
    assert events[0].frame_number == 2
    assert events[0].evidence["zone_id"] == "zoneA"
    assert events[0].evidence["previous_membership"] == "INSIDE"
    assert events[0].evidence["current_membership"] == "OUTSIDE"
    assert events[0].evidence["transition_type"] == "EXIT"

def test_repeated_transitions(engine):
    engine.process(1, 0.1, [create_obj(1, 15, 15)]) # OUTSIDE
    e1 = engine.process(2, 0.2, [create_obj(1, 5, 5)]) # INSIDE -> ENTRY
    e2 = engine.process(3, 0.3, [create_obj(1, 15, 15)]) # OUTSIDE -> EXIT
    e3 = engine.process(4, 0.4, [create_obj(1, 5, 5)]) # INSIDE -> ENTRY
    
    assert len(e1) == 1 and e1[0].event_type == EventType.ZONE_ENTRY
    assert len(e2) == 1 and e2[0].event_type == EventType.ZONE_EXIT
    assert len(e3) == 1 and e3[0].event_type == EventType.ZONE_ENTRY

def test_multiple_tracks_independent(engine):
    engine.process(1, 0.1, [create_obj(1, 15, 15), create_obj(2, 5, 5)]) # 1 OUT, 2 IN
    
    # Track 1 enters, Track 2 stays in
    events = engine.process(2, 0.2, [create_obj(1, 5, 5), create_obj(2, 6, 6)])
    assert len(events) == 1
    assert events[0].track_id == 1
    assert events[0].event_type == EventType.ZONE_ENTRY

def test_multiple_zones_independent(multi_engine):
    # Track starts OUTSIDE both
    multi_engine.process(1, 0.1, [create_obj(1, 50, 50)])
    
    # Track enters Zone A only
    events = multi_engine.process(2, 0.2, [create_obj(1, 5, 5)])
    assert len(events) == 1
    assert events[0].evidence["zone_id"] == "zoneA"
    assert events[0].event_type == EventType.ZONE_ENTRY

def test_temporary_absence_no_exit(engine):
    engine.process(1, 0.1, [create_obj(1, 5, 5)]) # INSIDE
    
    # Missing from update
    events_absent = engine.process(2, 0.2, [])
    assert len(events_absent) == 0
    
    # Reappears inside
    events_reappear = engine.process(3, 0.3, [create_obj(1, 6, 6)])
    assert len(events_reappear) == 0

def test_boundary_inclusive_policy(engine):
    engine.process(1, 0.1, [create_obj(1, 15, 15)]) # OUTSIDE
    
    # Moves exactly onto the boundary (x=10, y=5)
    events = engine.process(2, 0.2, [create_obj(1, 10, 5)])
    assert len(events) == 1
    assert events[0].event_type == EventType.ZONE_ENTRY

def test_event_ids_unique(engine):
    engine.process(1, 0.1, [create_obj(1, 15, 15)])
    e1 = engine.process(2, 0.2, [create_obj(1, 5, 5)])
    e2 = engine.process(3, 0.3, [create_obj(1, 15, 15)])
    assert e1[0].event_id != e2[0].event_id

def test_reset_clears_state(engine):
    engine.process(1, 0.1, [create_obj(1, 5, 5)]) # Starts INSIDE, no event
    
    engine.reset()
    
    # Appears outside. Since state was cleared, this is the "first observation" again
    events = engine.process(2, 0.2, [create_obj(1, 15, 15)])
    assert len(events) == 0
    
    # Enters. This will trigger ENTRY
    events_enter = engine.process(3, 0.3, [create_obj(1, 5, 5)])
    assert len(events_enter) == 1

def test_deterministic_ordering(multi_engine):
    multi_engine.process(1, 0.1, [create_obj(1, 15, 15), create_obj(2, 50, 50)])
    
    # Track 1 enters Zone A. Track 2 enters Zone B.
    events = multi_engine.process(2, 0.2, [create_obj(2, 25, 5), create_obj(1, 5, 5)]) # Reverse order in list
    
    assert len(events) == 2
    # Should be sorted by track_id
    assert events[0].track_id == 1
    assert events[0].evidence["zone_id"] == "zoneA"
    
    assert events[1].track_id == 2
    assert events[1].evidence["zone_id"] == "zoneB"

def test_remove_track_clears_specific_state(multi_engine):
    multi_engine.process(1, 0.1, [create_obj(1, 5, 5), create_obj(2, 25, 5)]) # 1 in A, 2 in B
    
    multi_engine.remove_track(1)
    
    # Track 1 appears outside. Because it was removed, this is "first observation", no exit event.
    # Track 2 appears outside. This is an exit.
    events = multi_engine.process(2, 0.2, [create_obj(1, 15, 15), create_obj(2, 50, 50)])
    
    assert len(events) == 1
    assert events[0].track_id == 2
    assert events[0].event_type == EventType.ZONE_EXIT
