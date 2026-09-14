from abc import ABC, abstractmethod
from typing import List
from app.services.tracking.models import TrackedObject
from app.services.events.models import Event

class EventEngine(ABC):
    """
    Abstract interface for generating behavioral events from tracked objects.
    """
    
    @abstractmethod
    def process(self, frame_number: int, timestamp_seconds: float, tracked_objects: List[TrackedObject]) -> List[Event]:
        """
        Process a new set of tracking observations and generate any derived behavioral events.
        
        Args:
            frame_number: The current sequence frame number.
            timestamp_seconds: The time in seconds of the current observation.
            tracked_objects: The tracking outcomes from the Tracker abstraction.
            
        Returns:
            A list of explicitly constructed Event objects based purely on observable tracking data.
        """
        pass
