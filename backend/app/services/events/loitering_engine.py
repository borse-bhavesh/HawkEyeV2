import uuid
from typing import Dict, List, Tuple
from pydantic import BaseModel
from app.services.events.event_engine import EventEngine
from app.services.events.models import Event, EventType
from app.services.events.zones import Zone, get_object_zone_membership, get_reference_point
from app.services.events.config import EventIntelligenceConfig
from app.services.tracking.models import TrackedObject

class LoiteringState(BaseModel):
    """
    Maintains minimal state for a single track's continuous presence within a zone.
    """
    first_inside_timestamp: float
    loitering_event_emitted: bool = False

class LoiteringEngine(EventEngine):
    """
    Concrete event engine that identifies LOITERING events.
    A LOITERING event occurs when an object is continuously present inside a configured
    zone for at least the configured duration threshold.
    """
    
    def __init__(self, config: EventIntelligenceConfig, zones: List[Zone]):
        """
        Initializes the engine with the loitering duration threshold and configured zones.
        """
        self._threshold = config.loitering_duration_seconds
        # Sort zones by ID to guarantee deterministic evaluation order
        self._zones = sorted(zones, key=lambda z: z.zone_id)
        
        # State: maps (track_id, zone_id) -> LoiteringState
        self._state: Dict[Tuple[int, str], LoiteringState] = {}

    def process(self, frame_number: int, timestamp_seconds: float, tracked_objects: List[TrackedObject]) -> List[Event]:
        """
        Process incoming tracked objects against configured zones and emit LOITERING events if
        continuous presence thresholds are met.
        """
        events: List[Event] = []
        
        # Ensure deterministic ordering
        sorted_objects = sorted(tracked_objects, key=lambda obj: obj.track_id)
        
        for obj in sorted_objects:
            track_id = obj.track_id
            
            for zone in self._zones:
                zone_id = zone.zone_id
                state_key = (track_id, zone_id)
                
                # Check spatial membership
                is_currently_inside = get_object_zone_membership(obj, zone)
                
                if is_currently_inside:
                    if state_key not in self._state:
                        # First observation inside this zone for this continuous interval
                        self._state[state_key] = LoiteringState(
                            first_inside_timestamp=timestamp_seconds
                        )
                    else:
                        # Object is continuing its presence inside the zone
                        state = self._state[state_key]
                        
                        if not state.loitering_event_emitted:
                            observed_duration = timestamp_seconds - state.first_inside_timestamp
                            
                            # Threshold check
                            if observed_duration >= self._threshold:
                                state.loitering_event_emitted = True
                                
                                ref_point = get_reference_point(obj.bounding_box)
                                
                                events.append(
                                    Event(
                                        event_id=str(uuid.uuid4()),
                                        event_type=EventType.LOITERING,
                                        frame_number=frame_number,
                                        timestamp_seconds=timestamp_seconds,
                                        description=(
                                            f"Track {track_id} remained inside zone '{zone.name}' "
                                            f"for {observed_duration:.1f} seconds, exceeding the configured "
                                            f"loitering threshold of {self._threshold:.1f} seconds."
                                        ),
                                        track_id=track_id,
                                        evidence={
                                            "zone_id": zone_id,
                                            "zone_name": zone.name,
                                            "presence_start_timestamp": state.first_inside_timestamp,
                                            "current_timestamp": timestamp_seconds,
                                            "observed_duration_seconds": observed_duration,
                                            "configured_threshold_seconds": self._threshold,
                                            "reference_point_x": ref_point.x,
                                            "reference_point_y": ref_point.y
                                        }
                                    )
                                )
                else:
                    # Object is OUTSIDE. Clear any ongoing continuous presence timer.
                    if state_key in self._state:
                        del self._state[state_key]
                        
        return events

    def reset(self) -> None:
        """
        Clears all internal loitering state.
        Allows for deterministic session boundaries.
        """
        self._state.clear()
        
    def remove_track(self, track_id: int) -> None:
        """
        Explicitly removes state tracking for a specific track.
        Called by lifecycle managers when a track is definitively ended.
        """
        keys_to_delete = [k for k in self._state.keys() if k[0] == track_id]
        for k in keys_to_delete:
            del self._state[k]
