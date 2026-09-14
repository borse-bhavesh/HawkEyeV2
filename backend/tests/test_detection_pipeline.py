from pathlib import Path
import pytest
import numpy as np

from app.services.frame_processor import FrameProcessor
from app.services.video_stream import VideoStream
from app.services.video_frame import VideoFrame
from app.services.detection.detector import Detector
from app.services.detection.models import Detection, BoundingBox
from app.services.detection.mock_detector import MockDetector

TEST_VIDEO = Path(__file__).parent / "fixtures" / "test_video.mp4"

class RecordingDetector(Detector):
    def __init__(self):
        self.received_frames = []

    def detect(self, frame: VideoFrame) -> list[Detection]:
        self.received_frames.append(frame)
        bbox = BoundingBox(x1=0.0, y1=0.0, x2=10.0, y2=10.0)
        return [Detection(class_id=0, class_name="rec", confidence=1.0, bounding_box=bbox)]

class EmptyDetector(Detector):
    def detect(self, frame: VideoFrame) -> list[Detection]:
        return []

class MultiDetector(Detector):
    def detect(self, frame: VideoFrame) -> list[Detection]:
        bbox1 = BoundingBox(x1=0.0, y1=0.0, x2=10.0, y2=10.0)
        det1 = Detection(class_id=1, class_name="cat", confidence=0.9, bounding_box=bbox1)
        bbox2 = BoundingBox(x1=20.0, y1=20.0, x2=30.0, y2=30.0)
        det2 = Detection(class_id=2, class_name="dog", confidence=0.8, bounding_box=bbox2)
        return [det1, det2]

def test_pipeline_detector_receives_videoframe():
    detector = RecordingDetector()
    processor = FrameProcessor(detector=detector)

    with VideoStream(TEST_VIDEO) as stream:
        processor.process(stream, max_frames=5)

    assert len(detector.received_frames) == 5
    for i, frame in enumerate(detector.received_frames):
        assert isinstance(frame, VideoFrame)
        assert frame.frame_number == i + 1

def test_pipeline_detector_processed_frames_only():
    detector = RecordingDetector()
    processor = FrameProcessor(detector=detector)

    with VideoStream(TEST_VIDEO) as stream:
        result = processor.process(stream, max_frames=3, frame_skip=1)

    assert result.frames_processed == 3
    assert result.frames_skipped == 2
    assert result.total_frames_read == 5
    
    assert len(detector.received_frames) == 3
    assert [f.frame_number for f in detector.received_frames] == [1, 3, 5]

def test_pipeline_max_frames_limits_calls():
    detector = RecordingDetector()
    processor = FrameProcessor(detector=detector)

    with VideoStream(TEST_VIDEO) as stream:
        result = processor.process(stream, max_frames=5, frame_skip=0)

    assert result.frames_processed == 5
    assert result.first_frame_number == 1
    assert result.last_frame_number == 5
    assert len(detector.received_frames) == 5

def test_pipeline_detector_returns_valid_detections():
    detector = MockDetector()
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=np.zeros((10, 10, 3)))
    
    results = detector.detect(frame)
    for det in results:
        assert isinstance(det, Detection)
        assert det.class_id >= 0
        assert len(det.class_name) > 0
        assert 0.0 <= det.confidence <= 1.0
        assert isinstance(det.bounding_box, BoundingBox)
        assert det.bounding_box.x2 > det.bounding_box.x1
        assert det.bounding_box.y2 > det.bounding_box.y1

def test_pipeline_empty_detection_valid():
    detector = EmptyDetector()
    processor = FrameProcessor(detector=detector)

    with VideoStream(TEST_VIDEO) as stream:
        result = processor.process(stream, max_frames=2)
    
    assert result.frames_processed == 2

def test_pipeline_multiple_detections():
    detector = MultiDetector()
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=np.zeros((10, 10, 3)))
    
    results = detector.detect(frame)
    assert len(results) == 2
    
    assert isinstance(results[0], Detection)
    assert results[0].class_id == 1
    assert results[0].class_name == "cat"
    
    assert isinstance(results[1], Detection)
    assert results[1].class_id == 2
    assert results[1].class_name == "dog"

def test_pipeline_deterministic_behavior():
    detector = MockDetector()
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=np.zeros((10, 10, 3)))
    
    results1 = detector.detect(frame)
    results2 = detector.detect(frame)
    
    assert results1 == results2
