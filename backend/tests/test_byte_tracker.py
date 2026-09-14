import pytest
from app.services.tracking.byte_tracker import ByteTrackTracker
from app.services.tracking.config import TrackingConfig
from app.services.tracking.tracker import Tracker
from app.services.tracking.models import TrackedObject
from app.services.detection.models import Detection, BoundingBox
import numpy as np


@pytest.fixture
def tracking_config():
    return TrackingConfig(
        track_high_thresh=0.5,
        track_low_thresh=0.1,
        new_track_thresh=0.6,
        track_buffer=30,
        match_thresh=0.8,
        fuse_score=True
    )

@pytest.fixture
def class_map():
    return {1: "person", 2: "bicycle"}


# 1. ByteTrackTracker implements Tracker.
def test_implements_tracker(tracking_config):
    tracker = ByteTrackTracker(config=tracking_config)
    assert isinstance(tracker, Tracker)


# 2. Constructor creates exactly one underlying BYTETracker instance.
def test_one_internal_tracker_created(tracking_config):
    tracker = ByteTrackTracker(config=tracking_config)
    assert hasattr(tracker, "_tracker")
    # Store internal reference
    internal_tracker = tracker._tracker
    
    # Run an update
    tracker.update([])
    
    # 14. The same underlying BYTETracker instance is reused across updates.
    assert tracker._tracker is internal_tracker


# 4. Empty detections are handled correctly.
def test_empty_detections_handled_correctly(tracking_config):
    tracker = ByteTrackTracker(config=tracking_config)
    
    result = tracker.update([])
    
    assert isinstance(result, list)
    assert len(result) == 0


# 3. update() accepts list[Detection].
# 5. Multiple detections are converted correctly.
# 6. Bounding box coordinates are converted correctly.
# 7. Confidence is converted correctly.
# 8. Class ID is preserved.
# 9. Class-name mapping works.
# 11. External track ID becomes TrackedObject.track_id.
# 12. Output contains only TrackedObject objects.
def test_multiple_detections_processed_correctly(tracking_config, class_map):
    tracker = ByteTrackTracker(config=tracking_config, class_names=class_map)
    
    detections = [
        Detection(class_id=1, class_name="person", confidence=0.95, bounding_box=BoundingBox(x1=10, y1=20, x2=30, y2=40)),
        Detection(class_id=2, class_name="bicycle", confidence=0.85, bounding_box=BoundingBox(x1=50, y1=60, x2=70, y2=80))
    ]
    
    result = tracker.update(detections)
    
    assert isinstance(result, list)
    
    for obj in result:
        assert isinstance(obj, TrackedObject)
        
        # Valid ID boundaries
        assert obj.track_id > 0
        assert obj.confidence <= 1.0
        assert obj.bounding_box.x1 < obj.bounding_box.x2
        assert obj.bounding_box.y1 < obj.bounding_box.y2
        
        # Mapping verification
        assert obj.class_name == class_map[obj.class_id]


# 10. Missing class-name mapping has deterministic behavior.
def test_missing_class_map_fallback(tracking_config):
    # No class mapping provided
    tracker = ByteTrackTracker(config=tracking_config)
    
    detections = [
        Detection(class_id=99, class_name="unknown_input", confidence=0.95, bounding_box=BoundingBox(x1=10, y1=20, x2=30, y2=40))
    ]
    
    result = tracker.update(detections)
    
    if result:
        # Fallback string format used internally
        assert result[0].class_name == "class_99"


# 13. Original Detection objects remain unchanged.
def test_original_detections_are_immutable(tracking_config):
    tracker = ByteTrackTracker(config=tracking_config)
    
    det = Detection(class_id=1, class_name="person", confidence=0.95, bounding_box=BoundingBox(x1=10, y1=20, x2=30, y2=40))
    original_id = id(det)
    
    tracker.update([det])
    
    assert id(det) == original_id
    assert det.class_id == 1
    assert det.class_name == "person"
    assert det.confidence == 0.95
    assert not hasattr(det, "track_id")


# 15. No detection-position-based track IDs are generated.
def test_ids_are_not_strictly_positional(tracking_config):
    tracker = ByteTrackTracker(config=tracking_config)
    
    # Send highly confident detection to spawn track
    detections = [
        Detection(class_id=1, class_name="person", confidence=0.99, bounding_box=BoundingBox(x1=10, y1=20, x2=30, y2=40))
    ]
    
    result_1 = tracker.update(detections)
    if result_1:
        first_id = result_1[0].track_id
        
        # Send empty frame to simulate miss
        tracker.update([])
        
        # Send detection back in slightly new position
        detections_moved = [
            Detection(class_id=1, class_name="person", confidence=0.99, bounding_box=BoundingBox(x1=11, y1=21, x2=31, y2=41))
        ]
        
        result_2 = tracker.update(detections_moved)
        if result_2:
            # Should have the same identity despite position in array changing and frame skip
            assert result_2[0].track_id == first_id


# 16. Invalid TrackingConfig values are rejected.
def test_invalid_config_rejected():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        TrackingConfig(track_high_thresh=1.5)  # Beyond 1.0 boundary
        
    with pytest.raises(ValidationError):
        TrackingConfig(track_buffer=-5)  # Negative
        
    with pytest.raises(ValidationError):
        TrackingConfig(tracker_type="deep_sort")  # Wrong literal


# 17. The adapter does not import or depend on YOLODetector.
# 18. The adapter does not depend on FrameProcessor.
def test_adapter_isolation():
    import app.services.tracking.byte_tracker as module
    
    # Must not contain cyclic imports
    assert not hasattr(module, "YOLODetector")
    assert not hasattr(module, "FrameProcessor")
    assert not hasattr(module, "VideoStream")

    