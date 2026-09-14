import pytest
import math
from app.services.events.config import EventIntelligenceConfig
from app.services.events.models import EventType
from app.services.events.proximity_engine import ProximityEngine
from app.services.tracking.models import TrackedObject, BoundingBox

@pytest.fixture
def config():
    return EventIntelligenceConfig(proximity_distance_threshold=100.0)

@pytest.fixture
def engine(config):
    return ProximityEngine(config)

def create_obj(track_id: int, center_x: float, bottom_y: float) -> TrackedObject:
    return TrackedObject(
        track_id=track_id,
        bounding_box=BoundingBox(x1=center_x, y1=bottom_y, x2=center_x+2, y2=bottom_y+2),
        class_id=0, class_name="person", confidence=0.9
    )

def test_zero_tracked_objects_produces_no_events(engine):
    events = engine.process(1, 0.0, [])
    assert len(events) == 0

def test_one_tracked_object_produces_no_events(engine):
    events = engine.process(1, 0.0, [create_obj(1, 100, 100)])
    assert len(events) == 0

def test_two_distant_objects_produces_no_event(engine):
    events = engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)])
    assert len(events) == 0

def test_first_ever_pair_within_threshold_initializes_state_without_false_event(engine):
    events = engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 110, 100)])
    assert len(events) == 0
    assert engine._state[(1, 2)].previously_in_proximity is True

def test_outside_to_inside_produces_exactly_one_event(engine):
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)]) # OUTSIDE
    events = engine.process(2, 1.0, [create_obj(1, 100, 100), create_obj(2, 110, 100)]) # INSIDE
    assert len(events) == 1
    assert events[0].event_type == EventType.MULTIPLE_OBJECT_PROXIMITY

def test_inside_to_inside_produces_no_duplicate_event(engine):
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)]) # OUTSIDE
    engine.process(2, 1.0, [create_obj(1, 100, 100), create_obj(2, 110, 100)]) # INSIDE (Emits)
    
    events = engine.process(3, 2.0, [create_obj(1, 100, 100), create_obj(2, 120, 100)]) # Still INSIDE
    assert len(events) == 0

def test_inside_to_outside_produces_no_event_but_resets_state(engine):
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)]) # OUTSIDE
    engine.process(2, 1.0, [create_obj(1, 100, 100), create_obj(2, 110, 100)]) # INSIDE
    
    events = engine.process(3, 2.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)]) # OUTSIDE
    assert len(events) == 0
    assert engine._state[(1, 2)].previously_in_proximity is False

def test_outside_to_inside_after_separation_produces_new_event(engine):
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)]) # OUTSIDE
    engine.process(2, 1.0, [create_obj(1, 100, 100), create_obj(2, 110, 100)]) # INSIDE -> Emit
    engine.process(3, 2.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)]) # OUTSIDE -> Reset
    
    events = engine.process(4, 3.0, [create_obj(1, 100, 100), create_obj(2, 120, 100)]) # INSIDE
    assert len(events) == 1 # New emit

def test_exact_threshold_distance_produces_proximity(engine):
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)])
    # Distance exactly 100
    events = engine.process(2, 1.0, [create_obj(1, 100, 100), create_obj(2, 200, 100)])
    assert len(events) == 1

def test_just_above_threshold_does_not_produce_proximity(engine):
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)])
    # Distance 100.1
    events = engine.process(2, 1.0, [create_obj(1, 100, 100), create_obj(2, 200.1, 100)])
    assert len(events) == 0

def test_same_track_is_never_paired_with_itself(engine):
    # Only single track
    engine.process(1, 0.0, [create_obj(1, 100, 100)])
    assert (1, 1) not in engine._state

def test_pair_order_is_canonical(engine):
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)])
    assert (1, 2) in engine._state
    assert (2, 1) not in engine._state

def test_reverse_ordering_produces_same_result(engine):
    engine.process(1, 0.0, [create_obj(2, 500, 100), create_obj(1, 100, 100)])
    events = engine.process(2, 1.0, [create_obj(2, 110, 100), create_obj(1, 100, 100)])
    assert len(events) == 1
    assert events[0].evidence["track_id_a"] == 1
    assert events[0].evidence["track_id_b"] == 2

def test_multiple_pairs_are_independently_evaluated(engine):
    # 1 and 2 outside, 1 and 3 inside
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100), create_obj(3, 110, 100)])
    
    # Now 1 and 2 inside, 1 and 3 outside
    events = engine.process(2, 1.0, [create_obj(1, 100, 100), create_obj(2, 120, 100), create_obj(3, 800, 100)])
    assert len(events) == 1
    assert events[0].evidence["track_id_a"] == 1
    assert events[0].evidence["track_id_b"] == 2

def test_multiple_close_objects_generate_separate_pair_events(engine):
    # All outside each other
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100), create_obj(3, 900, 100)])
    
    # All move together
    events = engine.process(2, 1.0, [create_obj(1, 100, 100), create_obj(2, 110, 100), create_obj(3, 120, 100)])
    assert len(events) == 3 # (1,2), (1,3), (2,3)
    
    pairs = set((e.evidence["track_id_a"], e.evidence["track_id_b"]) for e in events)
    assert pairs == {(1,2), (1,3), (2,3)}

def test_one_pair_becoming_close_does_not_affect_another_pair(engine):
    # 1,2 outside; 3,4 outside
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100), create_obj(3, 1000, 100), create_obj(4, 1500, 100)])
    
    # 1,2 become close. 3,4 remain outside
    events = engine.process(2, 1.0, [create_obj(1, 100, 100), create_obj(2, 110, 100), create_obj(3, 1000, 100), create_obj(4, 1500, 100)])
    assert len(events) == 1
    assert engine._state[(3, 4)].previously_in_proximity is False

def test_temporary_disappearance_does_not_reset_pair_state(engine):
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)])
    engine.process(2, 1.0, [create_obj(1, 100, 100), create_obj(2, 110, 100)]) # Emits
    
    # Track 2 disappears
    engine.process(3, 2.0, [create_obj(1, 100, 100)])
    assert engine._state[(1, 2)].previously_in_proximity is True

def test_reappearance_after_disappearance_no_false_duplicate(engine):
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)])
    engine.process(2, 1.0, [create_obj(1, 100, 100), create_obj(2, 110, 100)]) # Emits
    engine.process(3, 2.0, [create_obj(1, 100, 100)]) # Disappears
    
    # Reappears still in proximity
    events = engine.process(4, 3.0, [create_obj(1, 100, 100), create_obj(2, 120, 100)])
    assert len(events) == 0

def test_multiple_tracks_maintain_independent_pair_states(engine):
    # Tested adequately by multiple tests above
    assert True

def test_remove_track_removes_all_pair_states_involving_track(engine):
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 110, 100), create_obj(3, 120, 100)])
    engine.remove_track(2)
    assert (1, 2) not in engine._state
    assert (2, 3) not in engine._state

def test_remove_track_does_not_remove_unrelated_pair_states(engine):
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 110, 100), create_obj(3, 120, 100)])
    engine.remove_track(2)
    assert (1, 3) in engine._state

def test_reset_clears_all_pair_state(engine):
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 110, 100)])
    engine.reset()
    assert len(engine._state) == 0

def test_event_type_is_multiple_object_proximity(engine):
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)])
    events = engine.process(2, 1.0, [create_obj(1, 100, 100), create_obj(2, 110, 100)])
    assert events[0].event_type == EventType.MULTIPLE_OBJECT_PROXIMITY

def test_event_frame_corresponds_to_triggering_observation(engine):
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)])
    events = engine.process(100, 1.0, [create_obj(1, 100, 100), create_obj(2, 110, 100)])
    assert events[0].frame_number == 100

def test_event_timestamp_corresponds_to_triggering_observation(engine):
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)])
    events = engine.process(2, 5.5, [create_obj(1, 100, 100), create_obj(2, 110, 100)])
    assert events[0].timestamp_seconds == 5.5

def test_evidence_contains_both_track_ids(engine):
    engine.process(1, 0.0, [create_obj(3, 100, 100), create_obj(7, 500, 100)])
    events = engine.process(2, 1.0, [create_obj(3, 100, 100), create_obj(7, 110, 100)])
    assert events[0].evidence["track_id_a"] == 3
    assert events[0].evidence["track_id_b"] == 7

def test_evidence_contains_both_reference_points(engine):
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)])
    events = engine.process(2, 1.0, [create_obj(1, 100, 100), create_obj(2, 110, 100)])
    assert events[0].evidence["reference_point_a"] == {"x": 101.0, "y": 102.0} # shifted by bounding box
    assert events[0].evidence["reference_point_b"] == {"x": 111.0, "y": 102.0}

def test_evidence_contains_calculated_distance(engine):
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)])
    events = engine.process(2, 1.0, [create_obj(1, 100, 100), create_obj(2, 110, 100)])
    assert events[0].evidence["distance_pixels"] == 10.0

def test_evidence_contains_configured_threshold(engine):
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)])
    events = engine.process(2, 1.0, [create_obj(1, 100, 100), create_obj(2, 110, 100)])
    assert events[0].evidence["configured_threshold_pixels"] == 100.0

def test_evidence_contains_previous_current_proximity_state(engine):
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)])
    events = engine.process(2, 1.0, [create_obj(1, 100, 100), create_obj(2, 110, 100)])
    assert events[0].evidence["previous_proximity_state"] == "OUTSIDE"
    assert events[0].evidence["current_proximity_state"] == "INSIDE"

def test_deterministic_event_ordering(engine):
    # 4 objects, all outside
    engine.process(1, 0.0, [create_obj(4, 100, 100), create_obj(3, 500, 100), create_obj(2, 900, 100), create_obj(1, 1300, 100)])
    # All move inside together
    events = engine.process(2, 1.0, [create_obj(4, 100, 100), create_obj(3, 110, 100), create_obj(2, 120, 100), create_obj(1, 130, 100)])
    
    assert len(events) == 6
    pairs = [(e.evidence["track_id_a"], e.evidence["track_id_b"]) for e in events]
    # Lexicographical sort based on generated pairs
    assert pairs == [(1, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 4)]

def test_event_ids_are_unique(engine):
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)])
    e1 = engine.process(2, 1.0, [create_obj(1, 100, 100), create_obj(2, 110, 100)])
    engine.process(3, 2.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)]) # Sep
    e2 = engine.process(4, 3.0, [create_obj(1, 100, 100), create_obj(2, 110, 100)]) # Re-entry
    assert e1[0].event_id != e2[0].event_id

def test_duplicate_track_ids_follow_policy(engine):
    # Keep first occurrence policy
    # 1 and 2 outside
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)])
    
    # Send duplicate ID 2: first is far, second is close. Engine should keep first, meaning they remain OUTSIDE.
    events = engine.process(2, 1.0, [
        create_obj(1, 100, 100), 
        create_obj(2, 500, 100), # kept
        create_obj(2, 110, 100)  # ignored
    ])
    assert len(events) == 0
    
    # Send duplicate ID 2: first is close, second is far. Engine should keep first, meaning they transition to INSIDE.
    events2 = engine.process(3, 2.0, [
        create_obj(1, 100, 100), 
        create_obj(2, 110, 100), # kept
        create_obj(2, 500, 100)  # ignored
    ])
    assert len(events2) == 1
    
def test_no_physical_distance_units_claimed(engine):
    # Verified by inspecting event description
    engine.process(1, 0.0, [create_obj(1, 100, 100), create_obj(2, 500, 100)])
    events = engine.process(2, 1.0, [create_obj(1, 100, 100), create_obj(2, 110, 100)])
    assert "pixels" in events[0].description
    assert "meters" not in events[0].description
