from abc import ABC, abstractmethod

from app.services.detection.models import Detection
from app.services.tracking.models import TrackedObject


class Tracker(ABC):
    """
    Abstract interface for object tracking.
    
    Converts a list of frame detections into a list of temporally tracked objects.
    """

    @abstractmethod
    def update(self, detections: list[Detection]) -> list[TrackedObject]:
        """
        Process a list of detections from the current frame and update tracked objects.
        
        Args:
            detections: List of detections from the current frame.
            
        Returns:
            List of currently tracked objects.
        """
        raise NotImplementedError
