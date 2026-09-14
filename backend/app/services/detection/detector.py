from abc import ABC, abstractmethod
from app.services.video_frame import VideoFrame
from app.services.detection.models import Detection

class Detector(ABC):
    """
    Abstract interface for object detection.
    """

    @abstractmethod
    def detect(self, frame: VideoFrame) -> list[Detection]:
        """
        Perform detection on a single VideoFrame.
        """
        ...
