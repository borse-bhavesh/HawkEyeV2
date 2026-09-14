import pytest
from pathlib import Path

from app.services.frame_processor import FrameProcessor
from app.services.video_stream import VideoStream
from app.services.video_source import LocalVideoSource
from app.services.detection.detector import Detector
from app.services.detection.models import Detection, BoundingBox
from app.services.video_frame import VideoFrame
from app.services.detection.performance_config import DetectionPerformanceConfig

TEST_VIDEO = Path(__file__).parent / "fixtures" / "test_video.mp4"

class DummyDetector(Detector):
    def __init__(self):
        self.call_count = 0
        self.received_frames = []

    def detect(self, frame: VideoFrame) -> list[Detection]:
        self.call_count += 1
        self.received_frames.append(frame)
        bbox = BoundingBox(x1=0.0, y1=0.0, x2=10.0, y2=10.0)
        return [Detection(class_id=0, class_name="test", confidence=1.0, bounding_box=bbox)]

class MockClock:
    def __init__(self, start_time: float = 0.0):
        self.current_time = start_time
    def __call__(self) -> float:
        return self.current_time

def test_fps_limit_none():
    stream = VideoStream(TEST_VIDEO)
    stream.open()
    detector = DummyDetector()
    processor = FrameProcessor(detector=detector)
    result = processor.process(stream, max_frames=5)
    stream.close()
    
    assert detector.call_count == 5
    assert result.frames_processed == 5
    assert result.inference_frames_skipped == 0

def test_first_eligible_frame_immediately_sent():
    stream = VideoStream(TEST_VIDEO)
    stream.open()
    detector = DummyDetector()
    clock = MockClock(0.0)
    perf = DetectionPerformanceConfig(max_inference_fps=10)
    processor = FrameProcessor(detector=detector, performance_config=perf, clock=clock)
    
    result = processor.process(stream, max_frames=1)
    stream.close()
    
    assert detector.call_count == 1
    assert result.inference_frames_skipped == 0

def test_fps_limit_prevents_inference_before_interval():
    # max_fps = 10 -> interval = 0.1
    class SteppingClock(MockClock):
        def __init__(self):
            super().__init__()
            self.times = [0.0, 0.05, 0.09, 0.10, 0.15]
            self.index = 0
        def __call__(self) -> float:
            t = self.times[self.index]
            self.index += 1
            return t

    stream = VideoStream(TEST_VIDEO)
    stream.open()
    detector = DummyDetector()
    clock = SteppingClock()
    perf = DetectionPerformanceConfig(max_inference_fps=10)
    processor = FrameProcessor(detector=detector, performance_config=perf, clock=clock)
    
    result = processor.process(stream, max_frames=5)
    stream.close()
    
    assert detector.call_count == 2
    assert detector.received_frames[0].frame_number == 1
    assert detector.received_frames[1].frame_number == 4
    assert result.frames_processed == 5
    assert result.inference_frames_skipped == 3

def test_frame_after_allowed_interval_reaches_detector():
    class SteppingClock(MockClock):
        def __init__(self):
            super().__init__()
            self.times = [0.0, 0.11]
            self.index = 0
        def __call__(self) -> float:
            t = self.times[self.index]
            self.index += 1
            return t

    stream = VideoStream(TEST_VIDEO)
    stream.open()
    detector = DummyDetector()
    clock = SteppingClock()
    perf = DetectionPerformanceConfig(max_inference_fps=10)
    processor = FrameProcessor(detector=detector, performance_config=perf, clock=clock)
    
    result = processor.process(stream, max_frames=2)
    stream.close()
    
    assert detector.call_count == 2
    assert result.inference_frames_skipped == 0

def test_fps_limit_one_fps():
    # max_fps = 1 -> interval = 1.0
    class SteppingClock(MockClock):
        def __init__(self):
            super().__init__()
            self.times = [0.0, 0.5, 0.99, 1.0, 1.5]
            self.index = 0
        def __call__(self) -> float:
            t = self.times[self.index]
            self.index += 1
            return t

    stream = VideoStream(TEST_VIDEO)
    stream.open()
    detector = DummyDetector()
    clock = SteppingClock()
    perf = DetectionPerformanceConfig(max_inference_fps=1)
    processor = FrameProcessor(detector=detector, performance_config=perf, clock=clock)
    
    result = processor.process(stream, max_frames=5)
    stream.close()
    
    assert detector.call_count == 2
    assert detector.received_frames[0].frame_number == 1
    assert detector.received_frames[1].frame_number == 4
    assert result.frames_processed == 5
    assert result.inference_frames_skipped == 3

def test_frame_skip_and_fps_limit_work_together():
    # frame_skip = 1 -> frames 1, 3, 5 are processed.
    class SteppingClock(MockClock):
        def __init__(self):
            super().__init__()
            self.times = [0.0, 0.05, 0.1]
            self.index = 0
        def __call__(self) -> float:
            t = self.times[self.index]
            self.index += 1
            return t

    stream = VideoStream(TEST_VIDEO)
    stream.open()
    detector = DummyDetector()
    clock = SteppingClock()
    perf = DetectionPerformanceConfig(max_inference_fps=10)
    processor = FrameProcessor(detector=detector, performance_config=perf, clock=clock)
    
    result = processor.process(stream, max_frames=3, frame_skip=1)
    stream.close()
    
    assert result.frames_processed == 3
    assert result.frames_skipped == 2
    assert result.total_frames_read == 5
    
    assert detector.call_count == 2
    assert detector.received_frames[0].frame_number == 1
    assert detector.received_frames[1].frame_number == 5
    assert result.inference_frames_skipped == 1

