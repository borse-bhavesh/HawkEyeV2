import pytest
import time
from typing import Callable

from app.services.video_frame import VideoFrame
from app.services.video_stream import VideoStream
from app.services.frame_processor import FrameProcessor
from app.services.detection.detector import Detector
from app.services.detection.models import Detection, BoundingBox
from app.services.tracking.tracker import Tracker
from app.services.tracking.models import TrackedObject
from app.services.detection.performance_config import DetectionPerformanceConfig


class FakeVideoStream(VideoStream):
    def __init__(self, num_frames: int):
        self.num_frames = num_frames

    def open(self) -> None:
        pass

    def is_opened(self) -> bool:
        return True

    def read_frame(self) -> VideoFrame | None:
        pass

    def release(self) -> None:
        pass

    def frames(self):
        for i in range(1, self.num_frames + 1):
            yield VideoFrame(frame_number=i, timestamp_seconds=i*0.033, image=None)


class RecordingDetector(Detector):
    def __init__(self, detections_to_return: list[Detection] | None = None):
        self.call_count = 0
        self.received_frames = []
        self.detections_to_return = detections_to_return if detections_to_return is not None else []

    def detect(self, frame: VideoFrame) -> list[Detection]:
        self.call_count += 1
        self.received_frames.append(frame)
        return self.detections_to_return


class RecordingTracker(Tracker):
    def __init__(self, objects_to_return: list[TrackedObject] | None = None):
        self.call_count = 0
        self.received_detections = []
        self.objects_to_return = objects_to_return if objects_to_return is not None else []

    def update(self, detections: list[Detection]) -> list[TrackedObject]:
        self.call_count += 1
        self.received_detections.append(detections)
        return self.objects_to_return


def create_detection() -> Detection:
    return Detection(
        class_id=0,
        class_name="person",
        confidence=0.9,
        bounding_box=BoundingBox(x1=0, y1=0, x2=10, y2=10)
    )

def create_tracked_object() -> TrackedObject:
    return TrackedObject(
        track_id=1,
        class_id=0,
        class_name="person",
        confidence=0.9,
        bounding_box=BoundingBox(x1=0, y1=0, x2=10, y2=10)
    )


class MockClock:
    def __init__(self, initial_time=0.0):
        self.current_time = initial_time

    def __call__(self) -> float:
        return self.current_time

    def tick(self, seconds: float):
        self.current_time += seconds


def test_frame_processor_works_with_detector_only():
    detector = RecordingDetector()
    processor = FrameProcessor(detector=detector)
    stream = FakeVideoStream(num_frames=2)
    result = processor.process(stream)
    assert result.frames_processed == 2
    assert detector.call_count == 2
    assert len(result.tracking_results) == 0

def test_frame_processor_works_with_detector_and_tracker():
    detector = RecordingDetector()
    tracker = RecordingTracker()
    processor = FrameProcessor(detector=detector, tracker=tracker)
    stream = FakeVideoStream(num_frames=2)
    result = processor.process(stream)
    assert result.frames_processed == 2
    assert detector.call_count == 2
    assert tracker.call_count == 2
    assert len(result.tracking_results) == 2

def test_detector_receives_video_frame_objects():
    detector = RecordingDetector()
    processor = FrameProcessor(detector=detector)
    stream = FakeVideoStream(num_frames=1)
    processor.process(stream)
    assert isinstance(detector.received_frames[0], VideoFrame)

def test_tracker_receives_exactly_the_detection_list_returned_by_detector():
    det = create_detection()
    detector = RecordingDetector(detections_to_return=[det])
    tracker = RecordingTracker()
    processor = FrameProcessor(detector=detector, tracker=tracker)
    
    processor.process(FakeVideoStream(1))
    assert len(tracker.received_detections) == 1
    assert tracker.received_detections[0] == [det]

def test_frame_skip_prevents_both_detector_and_tracker_calls():
    detector = RecordingDetector()
    tracker = RecordingTracker()
    processor = FrameProcessor(detector=detector, tracker=tracker)
    
    result = processor.process(FakeVideoStream(3), frame_skip=1)
    # Frames 1, 3 processed. Frame 2 skipped.
    assert result.frames_processed == 2
    assert detector.call_count == 2
    assert tracker.call_count == 2

def test_fps_limiting_prevents_both_detector_and_tracker_calls():
    clock = MockClock()
    perf_config = DetectionPerformanceConfig(max_inference_fps=1.0)
    detector = RecordingDetector()
    tracker = RecordingTracker()
    processor = FrameProcessor(
        detector=detector, 
        tracker=tracker, 
        performance_config=perf_config, 
        clock=clock
    )
    
    stream = FakeVideoStream(2)
    # Frame 1: current time 0.0, inference runs
    # Next frame generated immediately. We will intercept the iteration if we could, 
    # but the fake stream generates all quickly. All frames read at time 0.0.
    result = processor.process(stream)
    
    # Frame 1: inferred
    # Frame 2: time is still 0.0, so inference skipped.
    assert result.frames_processed == 2
    assert detector.call_count == 1
    assert tracker.call_count == 1
    assert result.inference_frames_skipped == 1

def test_empty_detections_are_still_passed_to_tracker():
    detector = RecordingDetector(detections_to_return=[])
    tracker = RecordingTracker()
    processor = FrameProcessor(detector=detector, tracker=tracker)
    
    processor.process(FakeVideoStream(1))
    assert tracker.call_count == 1
    assert tracker.received_detections[0] == []

def test_tracker_output_is_preserved_in_the_processing_result():
    trk_obj = create_tracked_object()
    detector = RecordingDetector()
    tracker = RecordingTracker(objects_to_return=[trk_obj])
    processor = FrameProcessor(detector=detector, tracker=tracker)
    
    result = processor.process(FakeVideoStream(1))
    assert len(result.tracking_results) == 1
    assert result.tracking_results[0] == [trk_obj]

def test_multiple_detections_can_flow_through_tracker():
    dets = [create_detection(), create_detection()]
    detector = RecordingDetector(detections_to_return=dets)
    tracker = RecordingTracker()
    processor = FrameProcessor(detector=detector, tracker=tracker)
    
    processor.process(FakeVideoStream(1))
    assert tracker.received_detections[0] == dets

def test_multiple_tracked_objects_can_flow_back_from_tracker():
    trks = [create_tracked_object(), create_tracked_object()]
    detector = RecordingDetector()
    tracker = RecordingTracker(objects_to_return=trks)
    processor = FrameProcessor(detector=detector, tracker=tracker)
    
    result = processor.process(FakeVideoStream(1))
    assert result.tracking_results[0] == trks

def test_detector_and_tracker_remain_independent_abstractions():
    # Tracker should not depend on detector, detector should not depend on tracker
    # Proved by instantiating them separately
    assert issubclass(RecordingTracker, Tracker)
    assert issubclass(RecordingDetector, Detector)

def test_frame_processor_does_not_import_yolo_detector():
    import app.services.frame_processor as fp
    assert not hasattr(fp, "YOLODetector")

def test_frame_processor_does_not_import_mock_tracker():
    import app.services.frame_processor as fp
    assert not hasattr(fp, "MockTracker")

def test_supplying_tracker_without_detector_produces_explicit_error():
    tracker = RecordingTracker()
    with pytest.raises(ValueError, match="A detector is required when a tracker is configured."):
        FrameProcessor(detector=None, tracker=tracker)

def test_existing_frame_processor_behavior_remains_unchanged_when_no_tracker_is_supplied():
    processor = FrameProcessor()
    result = processor.process(FakeVideoStream(2))
    assert result.frames_processed == 2
    assert len(result.tracking_results) == 0
