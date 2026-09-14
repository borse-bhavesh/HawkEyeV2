import numpy as np
from app.services.detection.detector import Detector
from app.services.detection.mock_detector import MockDetector
from app.services.video_frame import VideoFrame
from app.services.detection.models import Detection

def test_mock_detector_instantiation():
    detector = MockDetector()
    assert isinstance(detector, MockDetector)
    assert isinstance(detector, Detector)

def test_mock_detector_returns_deterministic_results():
    detector = MockDetector()
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=np.zeros((10, 10, 3)))
    
    result = detector.detect(frame)
    
    assert isinstance(result, list)
    assert len(result) == 1
    
    det = result[0]
    assert isinstance(det, Detection)
    assert det.class_id == 0
    assert det.class_name == "person"
    assert 0.0 <= det.confidence <= 1.0
    assert det.confidence == 0.95
    
    # Check bounding box
    bbox = det.bounding_box
    assert bbox.x1 == 100.0
    assert bbox.y1 == 100.0
    assert bbox.x2 == 200.0
    assert bbox.y2 == 300.0

def test_mock_detector_repeated_calls():
    detector = MockDetector()
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=np.zeros((10, 10, 3)))
    
    result1 = detector.detect(frame)
    result2 = detector.detect(frame)
    
    assert result1 == result2

