import pytest

from app.services.frame_processor import FrameProcessor
from app.services.detection.detector import Detector
from app.services.detection.models import Detection, BoundingBox
from app.services.tracking.byte_tracker import ByteTrackTracker
from app.services.tracking.config import TrackingConfig
from app.services.tracking.mock_tracker import MockTracker
from app.services.video_stream import VideoStream
from app.services.video_frame import VideoFrame
from app.services.video_processing_response import VideoProcessingResponse


# ---------------------------------------------------------
# FAKES
# ---------------------------------------------------------

class ContractFakeVideoStream(VideoStream):
    def __init__(self, num_frames=3):
        self.num_frames = num_frames
        
    def open(self) -> None: pass
    def is_opened(self) -> bool: return True
    def read_frame(self) -> VideoFrame | None: pass
    def release(self) -> None: pass
    
    def frames(self):
        for i in range(1, self.num_frames + 1):
            yield VideoFrame(frame_number=i, timestamp_seconds=i*0.033, image=None)


class ScriptedDetector(Detector):
    def __init__(self, scripted_detections):
        self.scripted_detections = scripted_detections
        self.call_count = 0
        
    def detect(self, frame: VideoFrame) -> list[Detection]:
        # Return the detections for the current call count if we have them, else empty
        dets = []
        if self.call_count < len(self.scripted_detections):
            dets = self.scripted_detections[self.call_count]
        self.call_count += 1
        return dets


@pytest.fixture
def default_tracking_config():
    return TrackingConfig()


# ---------------------------------------------------------
# 1. FrameProcessor accepts ByteTrackTracker through Tracker abstraction.
# 2. Detector output reaches ByteTrackTracker.
# 3. ByteTrackTracker output reaches tracking_results.
# 4. One tracking result exists per processed frame.
# 9. Same ByteTrackTracker instance is reused across frames.
# ---------------------------------------------------------

def test_frame_processor_accepts_bytetrack_adapter(default_tracking_config):
    detector = ScriptedDetector([
        [Detection(class_id=1, class_name="person", confidence=0.9, bounding_box=BoundingBox(x1=10, y1=10, x2=20, y2=20))],
        [Detection(class_id=1, class_name="person", confidence=0.9, bounding_box=BoundingBox(x1=11, y1=11, x2=21, y2=21))],
    ])
    tracker = ByteTrackTracker(config=default_tracking_config, class_names={1: "person"})
    
    processor = FrameProcessor(detector=detector, tracker=tracker)
    
    # Store internal reference to check stateful reuse
    internal_tracker_instance = tracker._tracker
    
    result = processor.process(ContractFakeVideoStream(2))
    
    # 9. Ensure the same instance was kept alive
    assert tracker._tracker is internal_tracker_instance
    
    # 4. One tracking result exists per processed frame
    assert len(result.tracking_results) == 2
    
    # Verify the output successfully propagated through ByteTrack
    first_frame_tracks = result.tracking_results[0]
    assert len(first_frame_tracks) == 1
    assert first_frame_tracks[0].class_name == "person"
    assert first_frame_tracks[0].track_id >= 0


# ---------------------------------------------------------
# 10. Track identity can persist across sequential detections.
# 11. Multiple objects can be tracked.
# 12. Class IDs/classes are preserved.
# ---------------------------------------------------------

def test_track_identity_persists_for_multiple_objects(default_tracking_config):
    # Simulated object movement
    # Frame 1: Person A and Person B
    f1_dets = [
        Detection(class_id=1, class_name="person", confidence=0.9, bounding_box=BoundingBox(x1=10, y1=10, x2=20, y2=20)),
        Detection(class_id=1, class_name="person", confidence=0.8, bounding_box=BoundingBox(x1=50, y1=50, x2=60, y2=60))
    ]
    # Frame 2: Person A and B moved slightly
    f2_dets = [
        Detection(class_id=1, class_name="person", confidence=0.9, bounding_box=BoundingBox(x1=12, y1=12, x2=22, y2=22)),
        Detection(class_id=1, class_name="person", confidence=0.8, bounding_box=BoundingBox(x1=52, y1=52, x2=62, y2=62))
    ]
    
    detector = ScriptedDetector([f1_dets, f2_dets])
    tracker = ByteTrackTracker(config=default_tracking_config, class_names={1: "person"})
    
    processor = FrameProcessor(detector=detector, tracker=tracker)
    result = processor.process(ContractFakeVideoStream(2))
    
    tracks_f1 = result.tracking_results[0]
    tracks_f2 = result.tracking_results[1]
    
    assert len(tracks_f1) == 2
    assert len(tracks_f2) == 2
    
    # Identify objects by approximate position to extract their track IDs
    f1_obj1 = next(t for t in tracks_f1 if t.bounding_box.x1 < 30)
    f1_obj2 = next(t for t in tracks_f1 if t.bounding_box.x1 > 40)
    
    f2_obj1 = next(t for t in tracks_f2 if t.bounding_box.x1 < 30)
    f2_obj2 = next(t for t in tracks_f2 if t.bounding_box.x1 > 40)
    
    # Assert temporal identity persists
    assert f1_obj1.track_id == f2_obj1.track_id
    assert f1_obj2.track_id == f2_obj2.track_id
    
    # Assert distinct identities
    assert f1_obj1.track_id != f1_obj2.track_id
    
    # Verify class properties
    assert f1_obj1.class_name == "person"
    assert f1_obj1.class_id == 1


# ---------------------------------------------------------
# 8. Empty detections reach ByteTrackTracker.
# ---------------------------------------------------------

def test_empty_detections_reach_tracker(default_tracking_config):
    # Frame 1: Detection
    # Frame 2: Empty
    # Frame 3: Detection (moved slightly)
    
    f1_dets = [Detection(class_id=1, class_name="person", confidence=0.9, bounding_box=BoundingBox(x1=10, y1=10, x2=20, y2=20))]
    f2_dets = []
    f3_dets = [Detection(class_id=1, class_name="person", confidence=0.9, bounding_box=BoundingBox(x1=12, y1=12, x2=22, y2=22))]
    
    detector = ScriptedDetector([f1_dets, f2_dets, f3_dets])
    
    # Use a large track buffer so the track survives the empty frame
    config = TrackingConfig(track_buffer=30)
    tracker = ByteTrackTracker(config=config, class_names={1: "person"})
    
    processor = FrameProcessor(detector=detector, tracker=tracker)
    result = processor.process(ContractFakeVideoStream(3))
    
    assert len(result.tracking_results) == 3
    
    tracks_f1 = result.tracking_results[0]
    tracks_f2 = result.tracking_results[1]
    tracks_f3 = result.tracking_results[2]
    
    assert len(tracks_f1) == 1
    # Empty detection list returns empty tracker output for that frame
    assert len(tracks_f2) == 0
    # But because of track_buffer, the tracker preserved the internal Kalman state
    # and correctly matched the reappearing object.
    assert len(tracks_f3) == 1
    
    # Identity survived the blind frame!
    assert tracks_f1[0].track_id == tracks_f3[0].track_id


# ---------------------------------------------------------
# 5. frame_skip prevents tracker calls.
# 7. max_frames stops tracker processing correctly.
# ---------------------------------------------------------

def test_frame_skip_and_max_frames_integration(default_tracking_config):
    # 5 frames, skip 1 -> should process frames 1, 3, 5
    # With max_frames=3, it should stop after frame 3.
    # Total processed inference frames: Frame 1 and Frame 3 -> (2 tracker calls)
    
    detector = ScriptedDetector([
        [Detection(class_id=1, class_name="p", confidence=0.9, bounding_box=BoundingBox(x1=1, y1=1, x2=2, y2=2))],
        [Detection(class_id=1, class_name="p", confidence=0.9, bounding_box=BoundingBox(x1=1, y1=1, x2=2, y2=2))],
    ])
    tracker = ByteTrackTracker(config=default_tracking_config)
    
    processor = FrameProcessor(detector=detector, tracker=tracker)
    result = processor.process(ContractFakeVideoStream(5), frame_skip=1, max_frames=3)
    
    # Processed frames: 1, 3, 5
    assert detector.call_count == 3
    assert len(result.tracking_results) == 3


# ---------------------------------------------------------
# 6. FPS limiting prevents tracker calls.
# ---------------------------------------------------------

class MockClock:
    def __init__(self, time_sequence):
        self.times = time_sequence
        self.index = 0
    def __call__(self):
        t = self.times[self.index]
        self.index += 1
        return t

def test_fps_limiting_prevents_tracker_calls(default_tracking_config):
    detector = ScriptedDetector([
        [Detection(class_id=1, class_name="p", confidence=0.9, bounding_box=BoundingBox(x1=1, y1=1, x2=2, y2=2))],
        [Detection(class_id=1, class_name="p", confidence=0.9, bounding_box=BoundingBox(x1=1, y1=1, x2=2, y2=2))],
    ])
    tracker = ByteTrackTracker(config=default_tracking_config)
    
    # Max 10 FPS = 0.1s minimum delay between frames
    from app.services.detection.performance_config import DetectionPerformanceConfig
    perf_config = DetectionPerformanceConfig(max_inference_fps=10.0)
    processor = FrameProcessor(detector=detector, tracker=tracker, performance_config=perf_config)
    
    # Frame 1: 0.0s (Inferred)
    # Frame 2: 0.05s (Skipped, FPS limited)
    # Frame 3: 0.12s (Inferred)
    clock = MockClock([0.0, 0.05, 0.12])
    processor.clock = clock
    
    result = processor.process(ContractFakeVideoStream(3))
    
    # Only 2 frames inferred
    assert detector.call_count == 2
    assert len(result.tracking_results) == 2


# ---------------------------------------------------------
# 13. MockTracker remains compatible.
# ---------------------------------------------------------

def test_mock_tracker_remains_drop_in_compatible():
    detector = ScriptedDetector([[]])
    # Supplying the old mock tracker works cleanly
    tracker = MockTracker()
    processor = FrameProcessor(detector=detector, tracker=tracker)
    
    result = processor.process(ContractFakeVideoStream(1))
    assert len(result.tracking_results) == 1


# ---------------------------------------------------------
# 14. FrameProcessor contains no Ultralytics dependency.
# ---------------------------------------------------------

def test_frame_processor_dependency_isolation():
    import app.services.frame_processor as module
    assert not hasattr(module, "BYTETracker")
    assert not hasattr(module, "ultralytics")
    assert not hasattr(module, "ByteTrackTracker")


# ---------------------------------------------------------
# 15. Public API does not expose Ultralytics tracker objects.
# ---------------------------------------------------------

def test_api_boundary_protects_tracking_state():
    fields = VideoProcessingResponse.model_fields.keys()
    
    # The API object must NOT contain numpy arrays or Ultralytics objects.
    # The safest way is avoiding tracking attributes in the public schema altogether.
    assert "tracking_results" not in fields
    assert "tracker" not in fields
    assert "BYTETracker" not in fields
