import uuid
from typing import Dict, List, Tuple
from app.services.events.event_engine import EventEngine
from app.services.events.models import Event, EventType
from app.services.events.zones import Zone, get_object_zone_membership, get_reference_point
from app.services.tracking.models import TrackedObject

class ZoneEngine(EventEngine):
    """
    Concrete event engine that identifies ZONE_ENTRY and ZONE_EXIT
    events by monitoring spatial membership transitions over time.
    """
    
    def __init__(self, zones: List[Zone]):
        """
        Initializes the zone engine with a configured list of zones.
        """
        # Store zones sequentially to ensure deterministic processing order
        self._zones = sorted(zones, key=lambda z: z.zone_id)
        
        # State: maps (track_id, zone_id) -> bool (True if inside, False if outside)
        self._membership_state: Dict[Tuple[int, str], bool] = {}
        
    def process(self, frame_number: int, timestamp_seconds: float, tracked_objects: List[TrackedObject]) -> List[Event]:
        """
        Process incoming tracked objects against configured zones and emit transition events.
        """
        events: List[Event] = []
        
        # Process in deterministic order: track_id ascending, then zone_id ascending
        sorted_objects = sorted(tracked_objects, key=lambda obj: obj.track_id)
        
        for obj in sorted_objects:
            track_id = obj.track_id
            
            for zone in self._zones:
                zone_id = zone.zone_id
                state_key = (track_id, zone_id)
                
                # Calculate current spatial membership
                is_currently_inside = get_object_zone_membership(obj, zone)
                
                # Check previous state
                if state_key not in self._membership_state:
                    # Initial observation policy: record state but do NOT emit transition events
                    self._membership_state[state_key] = is_currently_inside
                    continue
                    
                was_previously_inside = self._membership_state[state_key]
                
                # Update internal state
                self._membership_state[state_key] = is_currently_inside
                
                # Evaluate transitions
                if not was_previously_inside and is_currently_inside:
                    # OUTSIDE -> INSIDE
                    ref_point = get_reference_point(obj.bounding_box)
                    events.append(
                        Event(
                            event_id=str(uuid.uuid4()),
                            event_type=EventType.ZONE_ENTRY,
                            frame_number=frame_number,
                            timestamp_seconds=timestamp_seconds,
                            description=f"Track {track_id} entered zone '{zone.name}'.",
                            track_id=track_id,
                            evidence={
                                "zone_id": zone_id,
                                "zone_name": zone.name,
                                "previous_membership": "OUTSIDE",
                                "current_membership": "INSIDE",
                                "transition_type": "ENTRY",
                                "reference_point_x": ref_point.x,
                                "reference_point_y": ref_point.y
                            }
                        )
                    )
                elif was_previously_inside and not is_currently_inside:
                    # INSIDE -> OUTSIDE
                    ref_point = get_reference_point(obj.bounding_box)
                    events.append(
                        Event(
                            event_id=str(uuid.uuid4()),
                            event_type=EventType.ZONE_EXIT,
                            frame_number=frame_number,
                            timestamp_seconds=timestamp_seconds,
                            description=f"Track {track_id} exited zone '{zone.name}'.",
                            track_id=track_id,
                            evidence={
                                "zone_id": zone_id,
                                "zone_name": zone.name,
                                "previous_membership": "INSIDE",
                                "current_membership": "OUTSIDE",
                                "transition_type": "EXIT",
                                "reference_point_x": ref_point.x,
                                "reference_point_y": ref_point.y
                            }
                        )
                    )
                # Note: OUTSIDE -> OUTSIDE and INSIDE -> INSIDE do nothing.
                # Note: Temporary disappearances are handled by simply doing nothing.
                # The TrackedObject is absent from the input list, so the loop above never runs for it,
                # meaning `self._membership_state[state_key]` remains unchanged during its absence.

        return events
        
    def reset(self) -> None:
        """
        Clears all internal membership state.
        Allows for deterministic session boundaries.
        """
        self._membership_state.clear()
        
    def remove_track(self, track_id: int) -> None:
        """
        Explicitly removes state tracking for a specific track, 
        typically called when the track lifecycle has ended.
        """
        keys_to_delete = [k for k in self._membership_state.keys() if k[0] == track_id]
        for k in keys_to_delete:
            del self._membership_state[k]
