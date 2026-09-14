import pytest
from pydantic import ValidationError

from app.services.detection.models import Detection, BoundingBox
from app.services.tracking.models import TrackedObject
from app.services.tracking.tracker import Tracker


def create_mock_detection() -> Detection:
    return Detection(
        class_id=0,
        class_name="person",
        confidence=0.8,
        bounding_box=BoundingBox(x1=0, y1=0, x2=10, y2=10)
    )

class FakeTracker(Tracker):
    def update(self, detections: list[Detection]) -> list[TrackedObject]:
        result = []
        for i, d in enumerate(detections):
            result.append(
                TrackedObject(
                    track_id=i,
                    class_id=d.class_id,
                    class_name=d.class_name,
                    confidence=d.confidence,
                    bounding_box=d.bounding_box
                )
            )
        return result


def test_tracker_is_abstract():
    with pytest.raises(TypeError):
        Tracker()

def test_concrete_tracker_implements_update():
    tracker = FakeTracker()
    assert hasattr(tracker, "update")

def test_concrete_tracker_accepts_list_of_detections():
    tracker = FakeTracker()
    detections = [create_mock_detection()]
    tracked = tracker.update(detections)
    assert isinstance(tracked, list)
    
def test_concrete_tracker_returns_list_of_tracked_objects():
    tracker = FakeTracker()
    detections = [create_mock_detection()]
    tracked = tracker.update(detections)
    assert len(tracked) == 1
    assert isinstance(tracked[0], TrackedObject)

def test_empty_detection_list_accepted():
    tracker = FakeTracker()
    tracked = tracker.update([])
    assert isinstance(tracked, list)

def test_empty_detection_list_produces_empty_tracked_object_list():
    tracker = FakeTracker()
    tracked = tracker.update([])
    assert len(tracked) == 0

def test_valid_detection_can_be_passed_to_tracker():
    tracker = FakeTracker()
    det = create_mock_detection()
    tracked = tracker.update([det])
    assert tracked[0].class_name == "person"

def test_returned_tracked_object_is_structurally_valid():
    tracker = FakeTracker()
    det = create_mock_detection()
    tracked = tracker.update([det])
    assert tracked[0].track_id == 0
    assert tracked[0].class_id == 0
    assert tracked[0].confidence == 0.8
    assert tracked[0].bounding_box.x2 == 10

def test_tracker_does_not_modify_detection_object():
    tracker = FakeTracker()
    det = create_mock_detection()
    original_conf = det.confidence
    tracker.update([det])
    assert det.confidence == original_conf

def test_detection_remains_without_track_id():
    det = create_mock_detection()
    assert not hasattr(det, "track_id")
    assert "track_id" not in Detection.model_fields.keys()

def test_tracker_does_not_depend_on_yolodetector():
    # Test statically checks there's no import of YOLODetector in tracker module
    import app.services.tracking.tracker as tracker_module
    assert not hasattr(tracker_module, "YOLODetector")
    assert not hasattr(tracker_module, "FrameProcessor")

def test_track_id_architectural_boundary():
    # Detection DOES NOT contain track_id
    assert "track_id" not in Detection.model_fields.keys()
    
    # TrackedObject DOES contain track_id
    assert "track_id" in TrackedObject.model_fields.keys()
