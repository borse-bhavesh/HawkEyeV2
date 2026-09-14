import pytest
from app.services.detection.models import Detection, BoundingBox
from app.services.tracking.models import TrackedObject
from app.services.tracking.tracker import Tracker
from app.services.tracking.mock_tracker import MockTracker

def create_detection(class_id: int, class_name: str, confidence: float) -> Detection:
    return Detection(
        class_id=class_id,
        class_name=class_name,
        confidence=confidence,
        bounding_box=BoundingBox(x1=0, y1=0, x2=10, y2=10)
    )

def test_mock_tracker_instantiation():
    tracker = MockTracker()
    assert tracker is not None

def test_mock_tracker_is_instance_of_tracker():
    tracker = MockTracker()
    assert isinstance(tracker, Tracker)

def test_empty_detection_list_returns_empty_list():
    tracker = MockTracker()
    tracked = tracker.update([])
    assert isinstance(tracked, list)
    assert len(tracked) == 0

def test_one_detection_produces_one_tracked_object():
    tracker = MockTracker()
    det = create_detection(0, "person", 0.9)
    tracked = tracker.update([det])
    assert len(tracked) == 1

def test_multiple_detections_produce_same_number_of_tracked_objects():
    tracker = MockTracker()
    detections = [
        create_detection(0, "person", 0.9),
        create_detection(2, "car", 0.8),
        create_detection(1, "bicycle", 0.7)
    ]
    tracked = tracker.update(detections)
    assert len(tracked) == 3

def test_first_detection_receives_track_id_1():
    tracker = MockTracker()
    detections = [create_detection(0, "person", 0.9)]
    tracked = tracker.update(detections)
    assert tracked[0].track_id == 1

def test_second_detection_receives_track_id_2():
    tracker = MockTracker()
    detections = [
        create_detection(0, "person", 0.9),
        create_detection(2, "car", 0.8)
    ]
    tracked = tracker.update(detections)
    assert tracked[1].track_id == 2

def test_third_detection_receives_track_id_3():
    tracker = MockTracker()
    detections = [
        create_detection(0, "person", 0.9),
        create_detection(2, "car", 0.8),
        create_detection(1, "bicycle", 0.7)
    ]
    tracked = tracker.update(detections)
    assert tracked[2].track_id == 3

def test_detection_class_id_is_preserved():
    tracker = MockTracker()
    det = create_detection(99, "unknown", 0.5)
    tracked = tracker.update([det])
    assert tracked[0].class_id == 99

def test_detection_class_name_is_preserved():
    tracker = MockTracker()
    det = create_detection(0, "person", 0.5)
    tracked = tracker.update([det])
    assert tracked[0].class_name == "person"

def test_detection_confidence_is_preserved():
    tracker = MockTracker()
    det = create_detection(0, "person", 0.87)
    tracked = tracker.update([det])
    assert tracked[0].confidence == 0.87

def test_detection_bounding_box_is_preserved_correctly():
    tracker = MockTracker()
    det = create_detection(0, "person", 0.87)
    det.bounding_box = BoundingBox(x1=5, y1=5, x2=20, y2=20)
    tracked = tracker.update([det])
    assert tracked[0].bounding_box.x1 == 5
    assert tracked[0].bounding_box.x2 == 20

def test_original_detection_objects_are_not_modified():
    tracker = MockTracker()
    det = create_detection(0, "person", 0.87)
    tracker.update([det])
    assert not hasattr(det, "track_id")

def test_repeated_calls_with_same_detection_list_produce_identical_results():
    tracker = MockTracker()
    detections = [
        create_detection(0, "person", 0.9),
        create_detection(2, "car", 0.8)
    ]
    tracked_1 = tracker.update(detections)
    tracked_2 = tracker.update(detections)
    
    assert tracked_1[0].track_id == tracked_2[0].track_id == 1
    assert tracked_1[1].track_id == tracked_2[1].track_id == 2

def test_different_detection_values_still_receive_deterministic_positional_ids():
    tracker = MockTracker()
    detections1 = [create_detection(0, "person", 0.9)]
    detections2 = [create_detection(2, "car", 0.8)]
    
    tracked_1 = tracker.update(detections1)
    tracked_2 = tracker.update(detections2)
    
    assert tracked_1[0].track_id == 1
    assert tracked_2[0].track_id == 1

def test_returned_objects_are_valid_tracked_object_instances():
    tracker = MockTracker()
    det = create_detection(0, "person", 0.9)
    tracked = tracker.update([det])
    assert isinstance(tracked[0], TrackedObject)

def test_returned_objects_satisfy_all_tracked_object_validation_rules():
    tracker = MockTracker()
    det = create_detection(0, "person", 0.9)
    tracked = tracker.update([det])
    # Pydantic validation runs automatically on instantiation. 
    # If it is successfully created without exception, it's valid.
    assert tracked[0].track_id == 1

def test_mock_tracker_handles_multiple_object_classes():
    tracker = MockTracker()
    detections = [
        create_detection(0, "person", 0.9),
        create_detection(2, "car", 0.8)
    ]
    tracked = tracker.update(detections)
    assert tracked[0].class_name == "person"
    assert tracked[1].class_name == "car"

def test_detection_remains_without_track_id():
    det = create_detection(0, "person", 0.9)
    assert not hasattr(det, "track_id")
    assert "track_id" not in Detection.model_fields.keys()

def test_mock_tracker_does_not_maintain_state_between_calls():
    tracker = MockTracker()
    detections = [create_detection(0, "person", 0.9)]
    tracked_1 = tracker.update(detections)
    
    detections_2 = [
        create_detection(2, "car", 0.8),
        create_detection(1, "bicycle", 0.7)
    ]
    tracked_2 = tracker.update(detections_2)
    
    # Second batch should start exactly at 1 because it's stateless.
    assert tracked_2[0].track_id == 1
    assert tracked_2[1].track_id == 2
