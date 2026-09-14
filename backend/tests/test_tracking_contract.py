import pytest
import sys
import importlib

from app.services.detection.models import Detection, BoundingBox
from app.services.tracking.models import TrackedObject
from app.services.tracking.tracker import Tracker
from app.services.frame_processor import FrameProcessor
from app.services.detection.detector import Detector
from app.services.video_frame import VideoFrame
from app.services.video_stream import VideoStream
from app.api.video import VideoProcessingResponse


# ---------------------------------------------------------
# FAKES FOR CONTRACT TESTING
# ---------------------------------------------------------

class ContractFakeTracker(Tracker):
    """A minimal Tracker to validate contract boundaries."""
    def __init__(self, objects_to_return=None):
        self.objects_to_return = objects_to_return if objects_to_return is not None else []
        self.call_count = 0
        self.received_detections = []
        
    def update(self, detections: list[Detection]) -> list[TrackedObject]:
        self.call_count += 1
        self.received_detections.append(detections)
        return self.objects_to_return


class ContractFakeDetector(Detector):
    def __init__(self, detections_to_return=None):
        self.detections_to_return = detections_to_return if detections_to_return is not None else []
        self.call_count = 0
        
    def detect(self, frame: VideoFrame) -> list[Detection]:
        self.call_count += 1
        return self.detections_to_return


class ContractFakeVideoStream(VideoStream):
    def __init__(self, num_frames=1):
        self.num_frames = num_frames
        
    def open(self) -> None: pass
    def is_opened(self) -> bool: return True
    def read_frame(self) -> VideoFrame | None: pass
    def release(self) -> None: pass
    
    def frames(self):
        for i in range(1, self.num_frames + 1):
            yield VideoFrame(frame_number=i, timestamp_seconds=i*0.033, image=None)


def create_sample_detection() -> Detection:
    return Detection(
        class_id=1,
        class_name="vehicle",
        confidence=0.95,
        bounding_box=BoundingBox(x1=10, y1=20, x2=30, y2=40)
    )


# ---------------------------------------------------------
# 2. TRACKER CONTRACT / 5. OUTPUT NORMALIZATION
# ---------------------------------------------------------

def test_tracker_returns_normalized_tracked_objects():
    tracker = ContractFakeTracker([
        TrackedObject(
            track_id=1, class_id=1, class_name="vehicle", confidence=0.95,
            bounding_box=BoundingBox(x1=10, y1=20, x2=30, y2=40)
        )
    ])
    result = tracker.update([create_sample_detection()])
    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], TrackedObject)


# ---------------------------------------------------------
# 4. DETECTION IMMUTABILITY
# ---------------------------------------------------------

def test_tracker_does_not_modify_detection():
    tracker = ContractFakeTracker()
    det = create_sample_detection()
    
    # Capture original state
    orig_class_id = det.class_id
    orig_class_name = det.class_name
    orig_conf = det.confidence
    orig_x1, orig_y1 = det.bounding_box.x1, det.bounding_box.y1
    orig_x2, orig_y2 = det.bounding_box.x2, det.bounding_box.y2
    
    tracker.update([det])
    
    # Verify input detection remains unchanged
    assert det.class_id == orig_class_id
    assert det.class_name == orig_class_name
    assert det.confidence == orig_conf
    assert det.bounding_box.x1 == orig_x1
    assert det.bounding_box.y1 == orig_y1
    assert det.bounding_box.x2 == orig_x2
    assert det.bounding_box.y2 == orig_y2
    assert not hasattr(det, "track_id")


# ---------------------------------------------------------
# 6. EMPTY INPUT CONTRACT
# ---------------------------------------------------------

def test_tracker_accepts_empty_input():
    tracker = ContractFakeTracker()
    result = tracker.update([])
    assert isinstance(result, list)
    assert len(result) == 0


# ---------------------------------------------------------
# 7. MULTIPLE DETECTION CONTRACT
# ---------------------------------------------------------

def test_tracker_accepts_multiple_detections():
    tracker = ContractFakeTracker()
    detections = [
        create_sample_detection(),
        create_sample_detection(),
        create_sample_detection()
    ]
    tracker.update(detections)
    assert tracker.received_detections[0] == detections
    assert len(tracker.received_detections[0]) == 3


# ---------------------------------------------------------
# 8. TRACK ID CONTRACT
# ---------------------------------------------------------

def test_track_id_contract_ge_zero():
    # Only structural validation (Pydantic model) is enforced.
    # Positive ID
    obj1 = TrackedObject(
        track_id=1, class_id=1, class_name="vehicle", confidence=0.95,
        bounding_box=BoundingBox(x1=10, y1=20, x2=30, y2=40)
    )
    assert obj1.track_id == 1
    
    # Zero ID
    obj2 = TrackedObject(
        track_id=0, class_id=1, class_name="vehicle", confidence=0.95,
        bounding_box=BoundingBox(x1=10, y1=20, x2=30, y2=40)
    )
    assert obj2.track_id == 0


# ---------------------------------------------------------
# 9. CLASS / BOUNDING BOX PRESERVATION
# ---------------------------------------------------------

def test_class_and_bounding_box_preservation():
    det = create_sample_detection()
    
    # Mimic a tracker that maps the input cleanly
    obj = TrackedObject(
        track_id=5,
        class_id=det.class_id,
        class_name=det.class_name,
        confidence=det.confidence,
        bounding_box=det.bounding_box
    )
    
    assert obj.class_id == det.class_id
    assert obj.class_name == det.class_name
    assert obj.confidence == det.confidence
    assert obj.bounding_box.x1 == det.bounding_box.x1


# ---------------------------------------------------------
# 10. FRAMEPROCESSOR CONTRACT
# ---------------------------------------------------------

def test_frame_processor_dependency_inversion():
    detector = ContractFakeDetector()
    tracker = ContractFakeTracker()
    processor = FrameProcessor(detector=detector, tracker=tracker)
    
    # Assert processor uses exactly the provided fakes, proving no hardcoded concrete types
    assert processor.detector is detector
    assert processor.tracker is tracker
    
    processor.process(ContractFakeVideoStream(1))
    assert detector.call_count == 1
    assert tracker.call_count == 1


# ---------------------------------------------------------
# 11. DETECTOR/TRACKER SEPARATION
# ---------------------------------------------------------

def test_module_separation_contracts():
    import app.services.tracking.tracker as tracker_module
    import app.services.frame_processor as processor_module
    
    # Tracker should not import Detector implementations
    assert not hasattr(tracker_module, "YOLODetector")
    
    # FrameProcessor should not import MockTracker or YOLODetector
    assert not hasattr(processor_module, "MockTracker")
    assert not hasattr(processor_module, "YOLODetector")


# ---------------------------------------------------------
# 12. TRACKER CALL ORDER
# ---------------------------------------------------------

def test_tracker_called_after_detector():
    call_order = []
    
    class OrderedFakeDetector(Detector):
        def detect(self, frame):
            call_order.append("detector")
            return []
            
    class OrderedFakeTracker(Tracker):
        def update(self, detections):
            call_order.append("tracker")
            return []
            
    processor = FrameProcessor(detector=OrderedFakeDetector(), tracker=OrderedFakeTracker())
    processor.process(ContractFakeVideoStream(1))
    
    assert call_order == ["detector", "tracker"]


# ---------------------------------------------------------
# 14. TRACKING RESULTS ALIGNMENT
# ---------------------------------------------------------

def test_tracking_results_alignment():
    tracker_results = [
        [TrackedObject(track_id=1, class_id=1, class_name="person", confidence=0.9, bounding_box=BoundingBox(x1=0, y1=0, x2=10, y2=10))],
        [TrackedObject(track_id=2, class_id=1, class_name="person", confidence=0.8, bounding_box=BoundingBox(x1=0, y1=0, x2=10, y2=10))]
    ]
    
    class SequenceFakeTracker(Tracker):
        def __init__(self):
            self.index = 0
            
        def update(self, detections):
            res = tracker_results[self.index]
            self.index += 1
            return res

    processor = FrameProcessor(
        detector=ContractFakeDetector(), 
        tracker=SequenceFakeTracker()
    )
    
    # Process 3 frames, but skip 1 frame
    # Frame 1: inferred -> tracking_results[0]
    # Frame 2: skipped
    # Frame 3: inferred -> tracking_results[1]
    result = processor.process(ContractFakeVideoStream(3), frame_skip=1)
    
    # Verify alignment length
    assert len(result.tracking_results) == 2
    
    # Verify ordering is exactly aligned with processed/inferred frames
    assert result.tracking_results[0] == tracker_results[0]
    assert result.tracking_results[1] == tracker_results[1]


# ---------------------------------------------------------
# 15. API BOUNDARY
# ---------------------------------------------------------

def test_api_boundary_does_not_expose_tracking():
    # VideoProcessingResponse should strictly define its schema and omit tracking_results.
    fields = VideoProcessingResponse.model_fields.keys()
    assert "tracking_results" not in fields
    assert "tracked_objects" not in fields
    assert "tracking" not in fields
