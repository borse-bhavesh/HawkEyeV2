from app.services.detection.detector import Detector
from app.services.video_frame import VideoFrame
from app.services.detection.models import Detection, BoundingBox

class MockDetector(Detector):
    """
    A deterministic mock detector that always returns the same set of detections
    for any given VideoFrame, without performing actual inference.
    """

    def detect(self, frame: VideoFrame) -> list[Detection]:
        bbox = BoundingBox(x1=100.0, y1=100.0, x2=200.0, y2=300.0)
        det = Detection(
            class_id=0,
            class_name="person",
            confidence=0.95,
            bounding_box=bbox
        )
        return [det]
