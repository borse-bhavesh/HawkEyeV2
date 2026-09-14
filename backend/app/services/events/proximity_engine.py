import uuid
import math
from typing import Dict, List, Tuple
from pydantic import BaseModel

from app.services.events.event_engine import EventEngine
from app.services.events.models import Event, EventType
from app.services.events.zones import get_reference_point
from app.services.events.config import EventIntelligenceConfig
from app.services.tracking.models import TrackedObject

class PairState(BaseModel):
    """
    Maintains minimal state for a unique pair of tracks.
    """
    previously_in_proximity: bool

class ProximityEngine(EventEngine):
    """
    Concrete event engine that identifies MULTIPLE_OBJECT_PROXIMITY events.
    An event occurs when two simultaneously observed objects transition from being
    separated to being within a configured spatial distance threshold.
    """
    
    def __init__(self, config: EventIntelligenceConfig):
        """
        Initializes the engine with the proximity distance threshold.
        """
        self._threshold = config.proximity_distance_threshold
        # State: maps canonical tuple (min_id, max_id) -> PairState
        self._state: Dict[Tuple[int, int], PairState] = {}

    def process(self, frame_number: int, timestamp_seconds: float, tracked_objects: List[TrackedObject]) -> List[Event]:
        """
        Process incoming tracked objects, evaluating unique canonical pairs for proximity.
        """
        events: List[Event] = []
        
        # Policy: duplicate track IDs in the same frame -> keep first occurrence deterministically
        unique_objects: List[TrackedObject] = []
        seen_ids = set()
        for obj in tracked_objects:
            if obj.track_id not in seen_ids:
                seen_ids.add(obj.track_id)
                unique_objects.append(obj)
                
        # Ensure deterministic pair ordering
        sorted_objects = sorted(unique_objects, key=lambda obj: obj.track_id)
        
        n = len(sorted_objects)
        
        for i in range(n):
            for j in range(i + 1, n):
                obj_a = sorted_objects[i]
                obj_b = sorted_objects[j]
                
                track_id_a = obj_a.track_id
                track_id_b = obj_b.track_id
                
                # Canonical ordering is inherently guaranteed since sorted_objects is sorted,
                # but explicit tuple definition ensures the map key matches.
                pair_key = (track_id_a, track_id_b)
                
                pt_a = get_reference_point(obj_a.bounding_box)
                pt_b = get_reference_point(obj_b.bounding_box)
                
                distance = math.sqrt((pt_a.x - pt_b.x)**2 + (pt_a.y - pt_b.y)**2)
                
                is_close = distance <= self._threshold
                
                if pair_key not in self._state:
                    # First observation of this pair
                    # Policy: establish state without emitting an event
                    if is_close:
                        self._state[pair_key] = PairState(previously_in_proximity=True)
                    else:
                        self._state[pair_key] = PairState(previously_in_proximity=False)
                    continue
                
                state = self._state[pair_key]
                
                if is_close and not state.previously_in_proximity:
                    # Transition: OUTSIDE -> INSIDE
                    state.previously_in_proximity = True
                    
                    events.append(
                        Event(
                            event_id=str(uuid.uuid4()),
                            event_type=EventType.MULTIPLE_OBJECT_PROXIMITY,
                            frame_number=frame_number,
                            timestamp_seconds=timestamp_seconds,
                            description=(
                                f"Tracks {track_id_a} and {track_id_b} were observed within "
                                f"{distance:.1f} pixels of each other, below the configured "
                                f"proximity threshold of {self._threshold:.1f} pixels."
                            ),
                            track_id=track_id_a, # Assign to first object conceptually
                            evidence={
                                "track_id_a": track_id_a,
                                "track_id_b": track_id_b,
                                "reference_point_a": {"x": pt_a.x, "y": pt_a.y},
                                "reference_point_b": {"x": pt_b.x, "y": pt_b.y},
                                "distance_pixels": distance,
                                "configured_threshold_pixels": self._threshold,
                                "previous_proximity_state": "OUTSIDE",
                                "current_proximity_state": "INSIDE"
                            }
                        )
                    )
                elif not is_close and state.previously_in_proximity:
                    # Transition: INSIDE -> OUTSIDE
                    state.previously_in_proximity = False

        return events

    def reset(self) -> None:
        """
        Clears all internal pair states.
        """
        self._state.clear()
        
    def remove_track(self, track_id: int) -> None:
        """
        Explicitly removes state tracking for all pairs involving a specific track.
        """
        keys_to_remove = [k for k in self._state.keys() if track_id in k]
        for k in keys_to_remove:
            del self._state[k]
