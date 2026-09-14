import uuid
import math
from typing import Dict, List
from pydantic import BaseModel
from app.services.events.event_engine import EventEngine
from app.services.events.models import Event, EventType
from app.services.events.zones import get_reference_point, Point2D
from app.services.events.config import EventIntelligenceConfig
from app.services.tracking.models import TrackedObject

class MovementState(BaseModel):
    """
    Maintains minimal state for a single track's movement history.
    """
    previous_reference_point: Point2D
    previous_timestamp: float
    rapid_movement_active: bool = False

class RapidMovementEngine(EventEngine):
    """
    Concrete event engine that identifies RAPID_MOVEMENT events.
    A RAPID_MOVEMENT event occurs when an object's calculated image-plane
    speed equals or exceeds a configured threshold.
    """
    
    def __init__(self, config: EventIntelligenceConfig):
        """
        Initializes the engine with the rapid movement speed threshold.
        """
        self._threshold = config.rapid_movement_speed_threshold
        # State: maps track_id -> MovementState
        self._state: Dict[int, MovementState] = {}

    def process(self, frame_number: int, timestamp_seconds: float, tracked_objects: List[TrackedObject]) -> List[Event]:
        """
        Process incoming tracked objects and emit RAPID_MOVEMENT events if
        speed thresholds are met.
        """
        events: List[Event] = []
        
        # Ensure deterministic ordering
        sorted_objects = sorted(tracked_objects, key=lambda obj: obj.track_id)
        
        for obj in sorted_objects:
            track_id = obj.track_id
            current_point = get_reference_point(obj.bounding_box)
            
            if track_id not in self._state:
                # First observation: cannot calculate speed
                self._state[track_id] = MovementState(
                    previous_reference_point=current_point,
                    previous_timestamp=timestamp_seconds,
                    rapid_movement_active=False
                )
                continue
                
            state = self._state[track_id]
            delta_t = timestamp_seconds - state.previous_timestamp
            
            # Policy: Ignore backwards timestamps
            if delta_t < 0:
                continue
                
            # Policy: Equal timestamps -> safely update point but calculate no speed
            if delta_t == 0:
                state.previous_reference_point = current_point
                state.previous_timestamp = timestamp_seconds
                continue
                
            # Calculate distance and speed
            dx = current_point.x - state.previous_reference_point.x
            dy = current_point.y - state.previous_reference_point.y
            distance = math.sqrt(dx**2 + dy**2)
            
            speed = distance / delta_t
            
            # Threshold evaluation
            is_rapid = speed >= self._threshold
            
            if is_rapid and not state.rapid_movement_active:
                # Transition: SLOW -> RAPID
                state.rapid_movement_active = True
                
                events.append(
                    Event(
                        event_id=str(uuid.uuid4()),
                        event_type=EventType.RAPID_MOVEMENT,
                        frame_number=frame_number,
                        timestamp_seconds=timestamp_seconds,
                        description=(
                            f"Track {track_id} moved at an observed image-plane rate of "
                            f"{speed:.1f} pixels/second, exceeding the configured threshold "
                            f"of {self._threshold:.1f} pixels/second."
                        ),
                        track_id=track_id,
                        evidence={
                            "previous_reference_point": {"x": state.previous_reference_point.x, "y": state.previous_reference_point.y},
                            "current_reference_point": {"x": current_point.x, "y": current_point.y},
                            "distance_pixels": distance,
                            "elapsed_seconds": delta_t,
                            "observed_speed_pixels_per_second": speed,
                            "configured_threshold_pixels_per_second": self._threshold,
                            "movement_state_transition": "SLOW_TO_RAPID"
                        }
                    )
                )
            elif not is_rapid and state.rapid_movement_active:
                # Transition: RAPID -> SLOW
                state.rapid_movement_active = False
            
            # Update state for next calculation
            state.previous_reference_point = current_point
            state.previous_timestamp = timestamp_seconds

        return events

    def reset(self) -> None:
        """
        Clears all internal movement state.
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
