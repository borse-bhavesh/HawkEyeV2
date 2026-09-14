from pathlib import Path

from app.services.frame_processor import FrameProcessor
from app.services.video_stream import VideoStream
from app.services.video_source import LocalVideoSource
from app.services.detection.detector import Detector
from app.services.detection.models import Detection, BoundingBox
from app.services.video_frame import VideoFrame


TEST_VIDEO = (
    Path(__file__).parent
    / "fixtures"
    / "test_video.mp4"
)


def test_frame_processor_processes_frames():
    stream = VideoStream(TEST_VIDEO)
    stream.open()

    processor = FrameProcessor()

    result = processor.process(
        stream,
        max_frames=10,
    )

    stream.close()

    assert result.frames_processed == 10
    assert result.first_frame_number == 1
    assert result.last_frame_number == 10
    assert result.total_frames_read == 10
    assert result.frames_skipped == 0


def test_frame_processor_processes_entire_video():
    stream = VideoStream(TEST_VIDEO)
    stream.open()

    processor = FrameProcessor()

    result = processor.process(stream)

    stream.close()

    assert result.frames_processed > 0
    assert result.first_frame_number == 1
    assert result.last_frame_number == result.frames_processed
    assert result.total_frames_read == 584
    assert result.frames_skipped == 0


def test_frame_processor_empty_limit():
    stream = VideoStream(TEST_VIDEO)
    stream.open()

    processor = FrameProcessor()

    result = processor.process(
        stream,
        max_frames=0,
    )

    stream.close()

    assert result.frames_processed == 1
    assert result.first_frame_number == 1
    assert result.last_frame_number == 1
    assert result.total_frames_read == 1
    assert result.frames_skipped == 0


def test_frame_processor_with_video_source():
    source = LocalVideoSource(TEST_VIDEO)

    stream = VideoStream(source)
    stream.open()

    processor = FrameProcessor()

    result = processor.process(
        stream,
        max_frames=10,
    )

    stream.close()

    assert result.frames_processed == 10
    assert result.first_frame_number == 1
    assert result.last_frame_number == 10
    assert result.total_frames_read == 10
    assert result.frames_skipped == 0


def test_frame_processor_frame_skip_one():
    stream = VideoStream(TEST_VIDEO)
    stream.open()

    processor = FrameProcessor()

    result = processor.process(
        stream,
        max_frames=5,
        frame_skip=1,
    )

    stream.close()

    assert result.frames_processed == 5
    assert result.first_frame_number == 1
    assert result.last_frame_number == 9
    assert result.total_frames_read == 9
    assert result.frames_skipped == 4


def test_frame_processor_frame_skip_two():
    stream = VideoStream(TEST_VIDEO)
    stream.open()

    processor = FrameProcessor()

    result = processor.process(
        stream,
        max_frames=5,
        frame_skip=2,
    )

    stream.close()

    assert result.frames_processed == 5
    assert result.first_frame_number == 1
    assert result.last_frame_number == 13
    assert result.total_frames_read == 13
    assert result.frames_skipped == 8


class DummyDetector(Detector):
    def __init__(self):
        self.call_count = 0
        self.received_frames = []

    def detect(self, frame: VideoFrame) -> list[Detection]:
        self.call_count += 1
        self.received_frames.append(frame)
        bbox = BoundingBox(x1=0.0, y1=0.0, x2=10.0, y2=10.0)
        return [Detection(class_id=0, class_name="test", confidence=1.0, bounding_box=bbox)]


def test_frame_processor_without_detector():
    processor = FrameProcessor()
    assert processor.detector is None


def test_frame_processor_with_detector():
    detector = DummyDetector()
    processor = FrameProcessor(detector=detector)
    assert processor.detector is detector


def test_frame_processor_calls_detector():
    stream = VideoStream(TEST_VIDEO)
    stream.open()
    detector = DummyDetector()
    processor = FrameProcessor(detector=detector)
    result = processor.process(stream, max_frames=5)
    stream.close()

    assert detector.call_count == 5
    assert len(detector.received_frames) == 5
    assert all(isinstance(f, VideoFrame) for f in detector.received_frames)
    assert result.frames_processed == 5


def test_frame_processor_detector_skips_frames():
    stream = VideoStream(TEST_VIDEO)
    stream.open()
    detector = DummyDetector()
    processor = FrameProcessor(detector=detector)
    result = processor.process(stream, max_frames=3, frame_skip=1)
    stream.close()

    assert detector.call_count == 3
    assert result.frames_processed == 3
    assert result.frames_skipped == 2
    assert result.total_frames_read == 5

from app.services.tracking.tracker import Tracker

class DummyTracker(Tracker):
    def update(self, detections):
        from app.services.tracking.models import TrackedObject
        return [TrackedObject(track_id=1, bounding_box=detections[0].bounding_box, class_id=0, class_name="test", confidence=1.0)]

def test_frame_processor_arrays_alignment():
    """
    Explicit test proving processed_frame_numbers[i], processed_timestamps[i], 
    and tracking_results[i] strictly represent the exact same frame.
    """
    stream = VideoStream(TEST_VIDEO)
    stream.open()
    detector = DummyDetector()
    tracker = DummyTracker()
    processor = FrameProcessor(detector=detector, tracker=tracker)
    
    # Process 3 frames with skip 1
    result = processor.process(stream, max_frames=3, frame_skip=1)
    stream.close()

    assert len(result.processed_frame_numbers) == 3
    assert len(result.processed_timestamps) == 3
    assert len(result.tracking_results) == 3

    # Frame skipping means frame numbers will be 1, 3, 5
    expected_frames = [1, 3, 5]
    
    for i in range(3):
        frame_num = result.processed_frame_numbers[i]
        ts = result.processed_timestamps[i]
        tracks = result.tracking_results[i]
        
        # Verify alignment: the actual received frame by the detector must match
        received_frame = detector.received_frames[i]
        
        assert frame_num == expected_frames[i]
        assert frame_num == received_frame.frame_number
        assert ts == received_frame.timestamp_seconds
        # DummyTracker just returns 1 track per detection
        assert len(tracks) == 1
        assert tracks[0].track_id == 1

