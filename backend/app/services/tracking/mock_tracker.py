from app.services.detection.models import Detection
from app.services.tracking.models import TrackedObject
from app.services.tracking.tracker import Tracker


class MockTracker(Tracker):
    """
    Deterministic mock implementation of the Tracker interface.
    
    This is strictly for unit testing and integration testing of the 
    detection-to-tracking pipeline. It assigns track_ids based on the 
    index position of the detection within the provided list.
    
    It maintains no state across frames and performs no real matching,
    IoU calculation, or temporal tracking.
    """

    def update(self, detections: list[Detection]) -> list[TrackedObject]:
        """
        Process detections and deterministically assign TrackedObjects.
        
        Args:
            detections: List of current frame detections.
            
        Returns:
            List of TrackedObjects where track_id = position + 1.
        """
        tracked_objects = []
        for i, detection in enumerate(detections):
            tracked_objects.append(
                TrackedObject(
                    track_id=i + 1,
                    class_id=detection.class_id,
                    class_name=detection.class_name,
                    confidence=detection.confidence,
                    bounding_box=detection.bounding_box
                )
            )
        return tracked_objects
