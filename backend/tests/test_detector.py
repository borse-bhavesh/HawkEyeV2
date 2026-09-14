import pytest
import numpy as np
from app.services.detection.detector import Detector
from app.services.video_frame import VideoFrame
from app.services.detection.models import Detection, BoundingBox

def test_detector_is_abstract():
    with pytest.raises(TypeError):
        Detector()

class MockDetector(Detector):
    def detect(self, frame: VideoFrame) -> list[Detection]:
        bbox = BoundingBox(x1=0.0, y1=0.0, x2=10.0, y2=10.0)
        det = Detection(class_id=1, class_name="mock", confidence=0.99, bounding_box=bbox)
        return [det]

def test_mock_detector_returns_list_of_detections():
    detector = MockDetector()
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=np.zeros((10, 10, 3)))
    
    result = detector.detect(frame)
    
    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], Detection)
    assert result[0].class_name == "mock"
