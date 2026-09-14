import uuid
import math
from typing import Dict, List, Optional
from pydantic import BaseModel

from app.services.events.event_engine import EventEngine
from app.services.events.models import Event, EventType
from app.services.events.zones import get_reference_point, Point2D
from app.services.events.config import EventIntelligenceConfig
from app.services.tracking.models import TrackedObject

class DirectionState(BaseModel):
    """
    Maintains minimal state for a single track's direction history.
    """
    previous_reference_point: Point2D
    previous_timestamp: float
    previous_direction_degrees: Optional[float] = None

class DirectionChangeEngine(EventEngine):
    """
    Concrete event engine that identifies DIRECTION_CHANGE events.
    A DIRECTION_CHANGE event occurs when an object's image-plane movement
    direction changes by an angle equal to or exceeding a configured threshold.
    """
    
    def __init__(self, config: EventIntelligenceConfig):
        """
        Initializes the engine with the direction change angle threshold.
        """
        self._threshold = config.direction_change_angle_threshold
        # State: maps track_id -> DirectionState
        self._state: Dict[int, DirectionState] = {}

    def process(self, frame_number: int, timestamp_seconds: float, tracked_objects: List[TrackedObject]) -> List[Event]:
        """
        Process incoming tracked objects and emit DIRECTION_CHANGE events if
        angular thresholds are met.
        """
        events: List[Event] = []
        
        # Ensure deterministic ordering
        sorted_objects = sorted(tracked_objects, key=lambda obj: obj.track_id)
        
        for obj in sorted_objects:
            track_id = obj.track_id
            current_point = get_reference_point(obj.bounding_box)
            
            if track_id not in self._state:
                # First observation: cannot calculate movement vector
                self._state[track_id] = DirectionState(
                    previous_reference_point=current_point,
                    previous_timestamp=timestamp_seconds,
                    previous_direction_degrees=None
                )
                continue
                
            state = self._state[track_id]
            delta_t = timestamp_seconds - state.previous_timestamp
            
            # Policy: Ignore backwards timestamps
            if delta_t < 0:
                continue
                
            # Calculate distance
            dx = current_point.x - state.previous_reference_point.x
            dy = current_point.y - state.previous_reference_point.y
            
            # Policy: Stationary object has no direction
            if dx == 0 and dy == 0:
                # Safely update observation so future movement continues from here
                state.previous_reference_point = current_point
                state.previous_timestamp = timestamp_seconds
                continue
                
            # Calculate current direction
            current_direction_degrees = math.degrees(math.atan2(dy, dx)) % 360.0
            
            if state.previous_direction_degrees is None:
                # This completes the first valid movement vector. No comparison possible yet.
                state.previous_direction_degrees = current_direction_degrees
                state.previous_reference_point = current_point
                state.previous_timestamp = timestamp_seconds
                continue
            
            # Compare current direction to previous direction
            diff = abs(current_direction_degrees - state.previous_direction_degrees)
            if diff > 180.0:
                diff = 360.0 - diff
                
            # Threshold evaluation
            if diff >= self._threshold:
                events.append(
                    Event(
                        event_id=str(uuid.uuid4()),
                        event_type=EventType.DIRECTION_CHANGE,
                        frame_number=frame_number,
                        timestamp_seconds=timestamp_seconds,
                        description=(
                            f"Track {track_id} changed observed image-plane movement direction "
                            f"by {diff:.1f} degrees, exceeding the configured threshold of "
                            f"{self._threshold:.1f} degrees."
                        ),
                        track_id=track_id,
                        evidence={
                            "previous_reference_point": {"x": state.previous_reference_point.x, "y": state.previous_reference_point.y},
                            "current_reference_point": {"x": current_point.x, "y": current_point.y},
                            "previous_direction_degrees": state.previous_direction_degrees,
                            "current_direction_degrees": current_direction_degrees,
                            "direction_change_degrees": diff,
                            "configured_threshold_degrees": self._threshold,
                            "previous_timestamp": state.previous_timestamp,
                            "current_timestamp": timestamp_seconds
                        }
                    )
                )
            
            # The current vector becomes the previous vector for the next comparison
            state.previous_direction_degrees = current_direction_degrees
            state.previous_reference_point = current_point
            state.previous_timestamp = timestamp_seconds

        return events

    def reset(self) -> None:
        """
        Clears all internal direction state.
        Allows for deterministic session boundaries.
        """
        self._state.clear()
        
    def remove_track(self, track_id: int) -> None:
        """
        Explicitly removes state tracking for a specific track.
        Called by lifecycle managers when a track is definitively ended.
        """
        if track_id in self._state:
            del self._state[track_id]
